## In the terminal, "export FLASK_APP=flask_demo" (without .py)
## flask run -h 0.0.0.0 -p 8888

import logging, sys
#logging.disable(sys.maxsize)

import os
import json
import lucene
import math
from datetime import datetime
from java.nio.file import Paths
from org.apache.lucene.store import NIOFSDirectory, MMapDirectory, SimpleFSDirectory
from org.apache.lucene.analysis.standard import StandardAnalyzer
from org.apache.lucene.analysis.core import StopAnalyzer
from org.apache.lucene.document import Document, Field, TextField, FieldType, StringField, StoredField
from org.apache.lucene.queryparser.classic import QueryParser, MultiFieldQueryParser
from org.apache.lucene.index import IndexWriter, IndexWriterConfig, FieldInfo, IndexOptions, DirectoryReader, Term
from org.apache.lucene.search import IndexSearcher, BoostQuery, Query, TermQuery, BooleanQuery, BooleanClause
from org.apache.lucene.search.similarities import BM25Similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from flask import Flask, render_template, request

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
                        
                        #Now a json dump
                        if len(json_data["Text URL"]) > 0:
                            doc.add(StringField("Text URL", json.dumps(json_data["Text URL"]), StringField.Store.YES))
                        else:
                            doc.add(StringField("Text URL", "", StringField.Store.YES))
                        
                        #Take all the comments
                        flatten_comment_body = ""
                        for comment in json_data["Comments"]:
                            if json_data["Comments"][comment] is not None and "Body" in json_data["Comments"][comment] and json_data["Comments"][comment]["Body"] is not None:
                                flatten_comment_body += " " + json_data["Comments"][comment]["Body"]
                        doc.add(Field("Comments", flatten_comment_body, contextType))
                        
                        #Create a DB or way to store and retrieve files for this comment data, this can be added on a later date.
                        '''
                        if len(json_data["Comments"]) > 0:
                            doc.add(StringField("Text URL", json.dumps(json_data["Comments"]), StringField.Store.YES))
                        else:
                            doc.add(StringField("Text URL", "", StringField.Store.YES))
                        '''
                        writer.addDocument(doc)
        writer.close()
        print("Index created.")
    except Exception as e:
        print("Error at indexing:", str(e))
    
def order_posts(posts, query, upvote_weight, time_weight, relevance_weight):
    ordered_posts = []
    title_weight = 0.2
    body_weight = 0.7
    comment_weight = 0.1

    vectorizer = TfidfVectorizer(stop_words='english')
    query_vector = vectorizer.fit_transform([query])
    
    for post in posts:
        relevance_score = post['Score'] if post['Score'] is not None else 0
        title_similarity = 0
        body_similarity = 0
        comment_similarity = 0

        if post['Title'] is not None:
            if query.lower() in post['Title'].lower():
                title_vector = vectorizer.transform([post['Title']])
                title_similarity = cosine_similarity(query_vector, title_vector)[0][0]
                relevance_score += title_weight * title_similarity * post['Score']

        if post['Body'] is not None:
            if query.lower() in post['Body'].lower():
                body_vector = vectorizer.transform([post['Body']])
                body_similarity = cosine_similarity(query_vector, body_vector)[0][0]
                relevance_score += body_weight * body_similarity * post['Score']
                
        if 'Comments' in post and post['Comments'] is not None:
            flatten_comment_body = ""
            for comment in post['Comments']:
                if comment['Body'] is not None:
                    flatten_comment_body += " " + comment['Body']
            if query.lower() in flatten_comment_body.lower():
                comment_vector = vectorizer.transform([flatten_comment_body])
                comment_similarity = cosine_similarity(query_vector, comment_vector)[0][0]
                relevance_score += comment_weight * comment_similarity * post['Score']
                
        timestamp_str = post['Timestamp']
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

        time_diff = (datetime.now() - timestamp).total_seconds() / 86400
        time_score = int(100 / (time_diff / 30 + 1))

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

    analyzer = StandardAnalyzer()
    parser = MultiFieldQueryParser(['Title', 'Body', 'Comment'], analyzer)

    query_terms = query.split()
    boolean_query = BooleanQuery.Builder()
    
    title_weight = 0.5
    body_weight = 0.4
    comment_weight = 0.1
    for term in query_terms:
        title_query = TermQuery(Term("Title", term))
        body_query = TermQuery(Term("Body", term))
        comment_query = TermQuery(Term("Comment", term))
        
        boost_title_query = BoostQuery(title_query, title_weight)
        boost_body_query = BoostQuery(body_query, body_weight)
        boost_comment_query = BoostQuery(comment_query, comment_weight)
        
        boolean_query.add(boost_title_query, BooleanClause.Occur.SHOULD)
        boolean_query.add(boost_body_query, BooleanClause.Occur.SHOULD)
        boolean_query.add(boost_comment_query, BooleanClause.Occur.SHOULD)
    topDocs = searcher.search(boolean_query.build(), 100).scoreDocs

    top_results = []
    for hit in topDocs:
        doc = searcher.doc(hit.doc)
        title = doc.get("Title")
        body = doc.get("Body")
        votes = doc.get("Upvotes")
        timestamp = doc.get("Timestamp")
        URL = doc.get("URL")
        Text_URL = doc.get("Text URL")
        top_results.append({"Score": hit.score, "Title": title, "Body": body, "Upvotes": votes, "Timestamp": timestamp, "URL": URL, "Text URL": Text_URL})
    return top_results


app = Flask(__name__)

lucene.initVM(vmargs=['-Djava.awt.headless=true'])    
json_dir_path = '/home/cs172/IRProjectPhase2/doc_folder'
path_obj = Paths.get(json_dir_path)
create_index_json_files(path_obj)

weights = {'relevance':(0.1, 0.1, 0.8), 'upvotes':(0.8, 0.1, 0.1), 'time':(0.1, 0.8, 0.1)}

@app.route('/')
def start():
    return render_template('search.html')

@app.route('/', methods = ['GET', 'POST'])
def query():
    if request.method == 'POST':
        query = request.form['query']
        query = query.strip()
        sort = request.form['sort']
        lucene.getVMEnv().attachCurrentThread()
        posts = retrieve_posts_pylucene(path_obj, query)
        results = order_posts(posts, query, weights[sort][0], weights[sort][1], weights[sort][2])
        return render_template('result.html', results = results, length = min(len(results), 10))
    return render_template('search.html')

app.run(host="0.0.0.0", port=5500)

