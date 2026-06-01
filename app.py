from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///droplet.db'
db = SQLAlchemy(app)


@app.route('/')
def hello():
    return 'Droplet alive'


@app.route('/storage')
def storage():
    files = [
        {
            'name': 'Project notes.md',
            'kind': 'Document',
            'size': '18 KB',
            'updated': 'Today',
            'locked': True,
        },
        {
            'name': 'Design assets.zip',
            'kind': 'Archive',
            'size': '42 MB',
            'updated': 'Yesterday',
            'locked': True,
        },
        {
            'name': 'Team photo.png',
            'kind': 'Image',
            'size': '2.4 MB',
            'updated': 'May 30',
            'locked': False,
        },
    ]
    return render_template('storage.html', files=files)


if __name__ == '__main__':
    app.run(debug=True)
