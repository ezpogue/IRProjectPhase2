## In the terminal, "export FLASK_APP=flask_demo" (without .py)
## flask run -h 0.0.0.0 -p 8888

import logging, sys

logging.disable(sys.maxsize)

import os
import json
import lucene
from datetime import datetime
from java.nio.file import Paths
from org.apache.lucene.store import NIOFSDirectory, MMapDirectory, SimpleFSDirectory
from org.apache.lucene.analysis.standard import StandardAnalyzer
from org.apache.lucene.document import Document, Field, TextField, FieldType
from org.apache.lucene.queryparser.classic import QueryParser, MultiFieldQueryParser
from org.apache.lucene.index import IndexWriter, IndexWriterConfig, FieldInfo, IndexOptions, DirectoryReader, Term
from org.apache.lucene.search import IndexSearcher, BoostQuery, Query, TermQuery
from org.apache.lucene.search.similarities import BM25Similarity


# from flask import request, Flask, render_template
# app = Flask(__name__)

def create_index_json_files(directory_path):
    analyzer = StandardAnalyzer()
    config = IndexWriterConfig(analyzer)
    config.setOpenMode(IndexWriterConfig.OpenMode.CREATE)

    metaType = FieldType()
    metaType.setStored(True)
    metaType.setTokenized(False)

    contextType = FieldType()
    contextType.setStored(True)
    contextType.setTokenized(True)
    contextType.setIndexOptions(IndexOptions.DOCS_AND_FREQS_AND_POSITIONS)

    try:
        store = SimpleFSDirectory(directory_path)
        writer = IndexWriter(store, config)

        for file_name in os.listdir(str(directory_path)):
            if file_name.endswith(".json"):
                file_path = os.path.join(str(directory_path), file_name)
                with open(file_path, "r") as json_file:
                    for line in json_file:
                        json_data = json.loads(line)
                        doc = Document()
                        # doc.add(Field("Author", json_data["Author"], TextField.TYPE_STORED))
                        doc.add(Field("Timestamp", json_data["Timestamp"], TextField.TYPE_STORED))
                        doc.add(Field("Body", json_data["Body"], TextField.TYPE_STORED))
                        doc.add(Field("Upvotes", json_data["Upvotes"], TextField.TYPE_STORED))
                        doc.add(Field("Title", json_data["Title"], TextField.TYPE_STORED))

                        writer.addDocument(doc)
        writer.close()
        print("Index created.")

    except Exception as e:
        print("Error at indexing:", str(e))


def order_posts(posts, query):
    ordered_posts = []

    for post in posts:
        relevance_score = post['Score'] if post['Score'] is not None else 0

        if post['Title'] is not None:
            if query.lower() in post['Title'].lower():
                relevance_score += post['Score']

        timestamp_str = post['Timestamp']
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")  # convert the timestamp string to datetime

        time_diff = (datetime.now() - timestamp).total_seconds() / 86400  # calculate the time difference in days
        time_score = int(100 / (time_diff + 1))  # +1 to avoid division by 0

        upvotes = int(post['Upvotes']) if post['Upvotes'] is not None else 0

        score = round((upvotes / 100 * 0.20) + (time_score * 0.30) + (relevance_score * 0.5), 3)
        ordered_posts.append((post, score))

    ordered_posts.sort(key=lambda x: x[1], reverse=True)

    # cancel this output later
    for post, score in ordered_posts[:10]:
        print("Post: {}, Weighted Score: {}".format(post, score))

    return ordered_posts


def retrieve_posts_pylucene(storedir, query):
    searchDir = NIOFSDirectory(storedir)
    searcher = IndexSearcher(DirectoryReader.open(searchDir))

    parser = MultiFieldQueryParser(['Title', 'Body'], StandardAnalyzer())
    term = Term("Body", query)  # Create a Term object for the query string
    termQuery = TermQuery(term)  # Create a TermQuery using the Term object

    topDocs = searcher.search(termQuery, 30).scoreDocs  # get top 30 then select 10 highest weighted score posts

    top_results = []
    for hit in topDocs:
        doc = searcher.doc(hit.doc)  # convert to Lucene Doc object
        title = doc.get("Title")
        body = doc.get("Body")
        votes = doc.get("Upvotes")
        timestamp = doc.get("Timestamp")
        top_results.append({"Score": hit.score, "Title": title, "Body": body, "Upvotes": votes, "Timestamp": timestamp})

    return top_results


'''
@app.route("/")
def home():
    return 'CS172 Project Phase 2'

@app.route("/abc")
def abc():
    return 'hello'

@app.route('/input', methods = ['POST', 'GET'])
def search():
    return render_template('search.html')

@app.route('/output', methods = ['POST', 'GET'])
def output():
    if request.method == 'GET':
        return f"Nothing"
    if request.method == 'POST':
        form_data = request.form
        query = form_data['query']
        print(f"this is the query: {query}")
        lucene.getVMEnv().attachCurrentThread()
        docs = retrieve('sample_lucene_index/', str(query))
        print(docs)

        return render_template('output.html',lucene_output = docs)'''

lucene.initVM(vmargs=['-Djava.awt.headless=true'])

if __name__ == "__main__":
    # app.run(debug=True)

    # change the path to dir later
    json_dir_path = '/home/cs172/IRProjectPhase2/doc_folder'
    path_obj = Paths.get(json_dir_path)
    # create_index_json_files(path_obj)
    query = 'happy'
    posts = retrieve_posts_pylucene(path_obj, query)
    fianl_result = order_posts(posts, query)

