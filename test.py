from flask import Flask, render_template, request

app = Flask(__name__)

results = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

@app.route('/')
def start():
    return render_template('search.html')

@app.route('/', methods = ['GET', 'POST'])
def query():
    if request.method == 'POST':
        query = request.form['query']
        query = query.strip().split(' ')
        #results = run function here with query
        return render_template('result.html', results = results, length = min(len(results), 10))
    return render_template('search.html')


app.run(host="0.0.0.0", port=5502)