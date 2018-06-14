# -*- coding: utf-8 -*-
import json
from datetime import datetime

from elasticsearch import Elasticsearch
from flask import Flask, make_response
from flask import abort
from flask import request, jsonify, flash
from flask_bootstrap import Bootstrap
from flask_login import LoginManager
from flask_moment import Moment
from flask_sqlalchemy import SQLAlchemy
from py2neo import Graph
from werkzeug.security import check_password_hash, generate_password_hash

from common.global_list import *
from webapi.webapimodels import User, Book, new_alchemy_encoder

app = Flask(__name__)

# 配置flask配置对象中键：SQLALCHEMY_DATABASE_URI
app.config.from_object('config')
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
# 配置flask配置对象中键：SQLALCHEMY_COMMIT_TEARDOWN,设置为True,应用会自动在每次请求结束后提交数据库中变动
app.config['SQLALCHEMY_COMMIT_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
db = SQLAlchemy()
db.init_app(app)
bootstrap = Bootstrap(app)
moment = Moment(app)
login_manger = LoginManager()
login_manger.session_protection = 'strong'
login_manger.login_view = 'blog.login'
login_manger.init_app(app)

es = Elasticsearch([HOST_PORT])


@login_manger.user_loader
def load_user(user_id):
    from app.model import User
    return User.query.get(int(user_id))


@app.route('/api/login', methods=['POST'])
def login():
    username = request.get_json().get('username')
    password = request.get_json().get('password')
    user = User.query.filter_by(username=username).first()
    if user is not None and check_password_hash(user.password, password):
        repjson = jsonify({'code': 1, 'message': '成功登录', 'username': user.username})
        return repjson
    else:
        flash('用户或密码错误')
        return jsonify({'code': 0, 'message': '用户名或密码错误'})


@app.route('/api/register', methods=['POST'])
def register():
    ""
    if not request.json or not 'username' in request.json:
        abort(400)

    username = request.get_json().get('username')
    user = User.query.filter_by(username=username).first()
    if user is not None:
        return jsonify({'code': 0, 'message': '用户名已存在！'})

    user = User(username=username,
                password=generate_password_hash(request.get_json().get('password')))
    db.session.add(user)
    db.session.commit()
    return jsonify({'code': 1, 'message': '注册成功'})


@app.route('/api/addBook', methods=['POST'])
def add_book():
    """
    新建小说
    :return: 新建成功 | 已经存在
    """
    if not request.json or not 'userid' in request.json or not 'bookname' in request.json:
        abort(400)

    bookname = request.get_json().get('bookname')
    book = Book.query.filter_by(bookname=bookname).first()
    if book is not None:
        return jsonify({'code': 0, 'message': '本小说已存在，请确认后新建！'})

    book = Book(
        bookname=request.get_json().get('bookname'),
        userid=request.get_json().get('userid'),
        createtime=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        bookstatus=0
    )
    db.session.add(book)
    db.session.commit()
    return jsonify({'code': 1, 'message': '新增小说成功'})


@app.route('/api/bookList', methods=['POST'])
def book_list():
    """
    获取当前用户图书列表
    :return: 当前用户图书列表
    """
    if not request.json or not 'userid' in request.json:
        abort(400)

    userid = request.get_json().get('userid')
    books = Book.query.filter_by(userid=userid)

    msgs = []
    for msg in books:
        msgs.append(msg)
    books_json = json.dumps(msgs, cls=new_alchemy_encoder(), check_circular=False)
    return jsonify(books_json)


@app.route('/api/detail', methods=['POST'])
def get_detail_by_eid():
    if not request.json or not 'eid' in request.json:
        abort(400)

    eid = request.get_json().get('eid')
    body = {"query": {"term": {"_id": eid}}}
    all_doc = es.search(index=NEWS_INDEX, doc_type=NEWS_TYPE, body=body)
    return jsonify(all_doc['hits']['hits'][0].get('_source'))


def chapter_add():
    """
    持久化章节信息至elasticsearch
    :return:
    """
    if not request.json or not 'bookid' in request.json:
        abort(400)
    try:
        chaptername = request.get_json().get('chaptername')
        chapterabstract = request.get_json().get('chapterabstract')
        chaptercontent = request.get_json().get('chaptercontent')
        bookid = request.get_json().get('bookid')
        chapterversion = 1
        create_date = datetime.now()
        edit_date = datetime.now()
        body = {"chaptername": chaptername, "chapterabstract": chapterabstract,
                "chaptercontent": chaptercontent, "bookid": bookid, "chapterversion": chapterversion,
                "chapterversion": chapterversion, "create_date": create_date, "edit_date": edit_date}

        es.search(index=CHAPTER_INDEX, doc_type=CHAPTER_TYPE, body=body)
        return jsonify({'code': 1, 'message': '新增章节成功'})
    except Exception as err:
        print(err)
        return jsonify({'code': 0, 'message': '新增章节失败'})


def chapter_edit():
    """
    更新ElasticSearch章节信息
    :return:
    """
    pass


@app.route('/api/graph_demo', methods=['GET'])
def graph_demo():
    cypher_query = "START   n = Node(14698)    MATCH(n) -->(x)    RETURN    x, n"
    graph = Graph(
        host=NEO4J_HOST,  # neo4j 搭载服务器的ip地址，ifconfig可获取到
        http_port=NEO4J_HTTP_PORT,  # neo4j 服务器监听的端口号
        user=NEO4J_USER,  # 数据库user name，如果没有更改过，应该是neo4j
        password=NEO4J_PASSWORD  # 自己设定的密码
    )

    x = graph.run(cypher_query)
    return jsonify(str(list(x._source.buffer)))


@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8888, debug=True)
