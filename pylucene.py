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
from org.apache.lucene.document import Document, Field, TextField, FieldType, StringField
from org.apache.lucene.queryparser.classic import QueryParser, MultiFieldQueryParser
from org.apache.lucene.index import IndexWriter, IndexWriterConfig, FieldInfo, IndexOptions, DirectoryReader, Term
from org.apache.lucene.search import IndexSearcher, BoostQuery, Query, TermQuery
from org.apache.lucene.search.similarities import BM25Similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

#from flask import request, Flask, render_template
#app = Flask(__name__)

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
                        doc.add(Field("ID", json_data["ID"], metaType))
                        doc.add(Field("Author", json_data["Author"], metaType))
                        doc.add(Field("Title", json_data["Title"], contextType))
                        doc.add(Field("Timestamp", json_data["Timestamp"], metaType))
                        doc.add(Field("Body", json_data["Body"], contextType))
                        doc.add(Field("Upvotes", json_data["Upvotes"], metaType))
                        doc.add(Field("Ratio", json_data["Ratio"], metaType))
                        doc.add(Field("Permalink", json_data["Permalink"], metaType))
                        doc.add(Field("URL", json_data["URL"], metaType))
                        
                        text_urls = []
                        for text_url_data in json_data["Text URL"]:
                            text_url = Document()
                            text_url.add(Field("Title", text_url_data[0], contextType))
                            text_url.add(Field("Link", text_url_data[1], metaType))
                            text_urls.append(text_url)
                        doc.add(Field("Text URL", text_urls, metaType))
                        
                        comments = []
                        for comment_data in json_data["Comments"]:
                            comment = Document()
                            comment.add(Field("Author"), comment_data["Author"], metaType)
                            comment.add(Field("Parent ID"), comment_data["Parent ID"], metaType)
                            comment.add(Field("Body"), comment_data["Body"], contextType)
                            comment.add(Field("Upvotes"), comment_data["Ups"], metaType)
                            comment.add(Field("Downvotes"), comment_data["Downs"], metaType)
                            comment.add(Field("Permalink"), comment_data["Permalink"], metaType)
                            
                            comment_text_urls = []
                            for comment_text_url_data in json_data["Text URL"]:
                                comment_text_url = Document()
                                comment_text_url.add(Field("Title", comment_text_url_data[0], contextType))
                                comment_text_url.add(Field("Link", comment_text_url_data[1], metaType))
                                comment_text_urls.append(text_url)
                            comment.add(Field("Text URL", text_urls, metaType))
                        doc.add(Field("Comments", comments, metaType))
                        writer.addDocument(doc)
        writer.close()
        print("Index created.")
    except Exception as e:
        print("Error at indexing:", str(e))


"""def order_posts(posts, query):
    ordered_posts = []

    for post in posts:
        relevance_score = post['Score'] if post['Score'] is not None else 0

        if post['Title'] is not None:
            if query.lower() in post['Title'].lower():
                relevance_score += post['Score']
        
        if post['Body'] is not None:
            if query.lower() in post['Body'].lower():
                relevance_score += post['Score']

        timestamp_str = post['Timestamp']
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")   # convert the timestamp string to datetime

        time_diff = (datetime.now() - timestamp).total_seconds() / 86400    # calculate the time difference in days
        time_score = int(100 / (time_diff /30+ 1))                             # +1 to avoid division by 0

        upvotes = int(post['Upvotes']) if post['Upvotes'] is not None else 0

        score = round((upvotes / 100 * 0.20) + (time_score * 0.30) + (relevance_score * 0.5), 3)
        ordered_posts.append((post, score))

    ordered_posts.sort(key=lambda x: x[1], reverse=True)

    # cancel this output later
    for post, score in ordered_posts[:10]:
        print("Post: {}, Weighted Score: {}".format(post, score))

    return ordered_posts"""
    
def order_posts(posts, query, upvote_weight, time_weight, relevance_weight):
    ordered_posts = []

    # Calculate the query vector using TF-IDF
    vectorizer = TfidfVectorizer()
    query_vector = vectorizer.fit_transform([query])

    for post in posts:
        relevance_score = post['Score'] if post['Score'] is not None else 0
        title_similarity = 0
        body_similarity = 0
        if post['Title'] is not None:
            if query.lower() in post['Title'].lower():
                # Calculate the title vector using TF-IDF
                title_vector = vectorizer.transform([post['Title']])
                # Calculate the cosine similarity between query and title
                title_similarity = cosine_similarity(query_vector, title_vector)[0][0]
                # Update relevance score with title similarity
                relevance_score += title_similarity * post['Score']

        if post['Body'] is not None:
            if query.lower() in post['Body'].lower():
                # Calculate the body vector using TF-IDF
                body_vector = vectorizer.transform([post['Body']])
                # Calculate the cosine similarity between query and body
                body_similarity = cosine_similarity(query_vector, body_vector)[0][0]
                # Update relevance score with body similarity
                relevance_score += body_similarity * post['Score']

        timestamp_str = post['Timestamp']
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")   # convert the timestamp string to datetime

        time_diff = (datetime.now() - timestamp).total_seconds() / 86400    # calculate the time difference in days
        time_score = int(100 / (time_diff / 30 + 1))                        # +1 to avoid division by 0

        upvotes = int(post['Upvotes']) if post['Upvotes'] is not None else 0

        score = round(((upvotes / 1000) * upvote_weight) + (time_score * time_weight) + (relevance_score * relevance_weight), 3)
        ordered_posts.append((post, score))
    ordered_posts.sort(key=lambda x: x[1], reverse=True)

    for post, score in ordered_posts[:10]:
        print("Post: {}, Weighted Score: {}".format(post, score))

    return ordered_posts


def retrieve_posts_pylucene(storedir, query):
    searchDir = NIOFSDirectory(storedir)
    searcher = IndexSearcher(DirectoryReader.open(searchDir))

    parser = MultiFieldQueryParser(['Title', 'Body'], StandardAnalyzer())
    term = Term("Body", query)              # Create a Term object for the query string
    termQuery = TermQuery(term)             # Create a TermQuery using the Term object

    topDocs = searcher.search(termQuery, 30).scoreDocs     # get top 30 then select 10 highest weighted score posts

    top_results = []
    for hit in topDocs:
        doc = searcher.doc(hit.doc)                          # convert to Lucene Doc object
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

    #change the path to dir later
    json_dir_path = '/home/cs172/IRProjectPhase2/doc_folder'
    path_obj = Paths.get(json_dir_path)
    #create_index_json_files(path_obj)
    query = 'embarrassing'
    posts = retrieve_posts_pylucene(path_obj, query)
    fianl_result = order_posts(posts, query)

