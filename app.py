from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///droplet.db'
db = SQLAlchemy(app)

@app.route('/')
def hello():
    return '💧 Droplet alive'

if __name__ == '__main__':
    app.run(debug=True)
