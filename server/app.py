#!/usr/bin/env python3

from flask import Flask, session, make_response, jsonify, request
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
import os
from flask_migrate import Migrate
from models import db, Article, User
from flask_restful import Api, Resource
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy.exc import IntegrityError
import cloudinary
import cloudinary.uploader
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['SQLALCHEMY_DATABASE_URI']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.json.compact = False
app.config['SESSION_COOKIE_SECURE'] = True
app.config['REMEMBER_COOKIE_SECURE'] = True
app.config['CLOUDINARY_CLOUD_NAME'] = os.environ['CLOUDINARY_CLOUD_NAME']
app.config['CLOUDINARY_API_KEY'] = os.environ['CLOUDINARY_API_KEY']
app.config['CLOUDINARY_API_SECRET'] = os.environ['CLOUDINARY_API_SECRET']

bcrypt = Bcrypt(app=app)

migrate = Migrate(app=app, db=db)

db.init_app(app)

api = Api(app)

CORS(app, origins=["https://blog-project-frontend-omega.vercel.app"])

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=['200 per day', '75 per hour'] #Remember to edit this
)

cloudinary.config(
    cloud_name = app.config['CLOUDINARY_CLOUD_NAME'],
    api_key = app.config['CLOUDINARY_API_KEY'],
    api_secret = app.config['CLOUDINARY_API_SECRET']
)

class ClearSession(Resource):
    def delete(self):
        session['page_views'] = None
        session['user_id'] = None

        return {}, 204
    
class IndexArticle(Resource):
    def get(self):
        articles = [article.to_dict() for article in Article.query.all()]
        return articles, 200
    
class ShowArticle(Resource):
    def get(self, id):
        session['page_views'] = 0 if not session.get('page_views') else session.get('page_views')
        session['page_views'] += 1

        if session['page_views'] <= 100: #change this
            article = Article.query.filter(Article.id == id).first()
            article_json = jsonify(article.to_dict())

            return make_response(article_json, 200)
        return {"message": "Maximum pageview limit reached"}, 401
    
class GetArticle(Resource):
    def get(self):
        user_id = session.get('user_id')
        if not user_id:
            return {"Error": "Unauthorized"}, 401
        
        articles = Article.query.filter_by(user_id=user_id).all()

        return [article.to_dict() for article in articles], 200

class CreateArticle(Resource):
    decorators = [limiter.limit("100 per hour")]

    def post(self):
        user_id = session.get('user_id')
        if not user_id:
            return {'Error': 'Unauthorized. Please log in'}, 401
        
        user = User.query.get(user_id)
        if not user:
            return {'Error': 'User not found'}, 404
        
        data = request.get_json()
        required_fields = ['title', 'content', 'preview_text', 'minutes_to_read']
        
        if not all(field in data for field in required_fields):
            return {'Error': f'Missing required fields: {required_fields}'}, 400

        allowed_tags = ['Product', 'Engineering', 'Design']
        if 'tag' in data and data['tag'] not in allowed_tags:
            return {'error': f'Invalid tag. Allowed values: {allowed_tags}'}, 400

        try:
            article_data = {
                'author': user.username,
                'title': data['title'],
                'content': data['content'],
                'preview_text': data['preview_text'],
                'minutes_to_read': data['minutes_to_read'],
                'user_id': user_id,
                'tag': data.get('tag'), 
                'preview_image': data.get('preview_image')
            }

            article_data = {k: v for k, v in article_data.items() if v is not None}

            article = Article(**article_data)
            db.session.add(article)
            db.session.commit()
            
            return article.to_dict(), 201

        except (IntegrityError, ValueError) as e:
            db.session.rollback()
            return {'Error': str(e)}, 400
    
class Login(Resource):
    decorators = [limiter.limit("5 per minute")] 

    def post(self):
        username = request.get_json()['username']
        password = request.get_json()['password']

        if not username or not password:
            return {'error': 'Username and password are required'}, 400
        
        user = User.query.filter_by(username=username).first()

        if user and user.authenticate(password):
            session['user_id'] = user.id
            return user.to_dict(), 200
        return {"Error": "Invalid credentials"}, 401
    
class SignUp(Resource):
    decorators = [limiter.limit("3 per hour")] 

    def post(self):
        username = request.get_json()['username']
        password = request.get_json()['password']

        if not username or not password:
            return {"Error": "Username and password are required"}, 400
        
        if User.query.filter_by(username=username).first():
            return {"Error": "Username already exists"}, 409
        
        try:
            user = User(username=username)
            user.password_hash = password
            db.session.add(user)
            db.session.commit()

            session['user_id'] = user.id
            return user.to_dict(), 201
        
        except ValueError as e:
            return {"error": str(e)}, 400
    
class Logout(Resource):
    def delete(self):
        session['user_id'] = None
        return '', 204
    
class CheckSession(Resource):
    def get(self):
        user = User.query.filter(User.id == session.get('user_id')).first()

        if user:
            return (user.to_dict()), 200
        return {}, 401
    
# Update avatar method for later

class UploadImage(Resource):
    def post(self):
        user_id = session.get('user_id')
        if not user_id:
            return {'error': 'Unauthorized'}, 401
        
        if 'image' not in request.files:
            return {'error': 'No image provided'}, 400
        
        file = request.files['image']
        if file.filename == '':
            return {'error': 'No selected file'}, 400

        try:
            upload_result = cloudinary.uploader.upload(
                file,
                folder="article_images",
                allowed_formats=["jpg", "png", "jpeg", "gif"],
                transformation=[{"width": 1200, "height": 630, "crop": "limit"}]
            )
            return upload_result, 200
        except Exception as e:
            return {'error': str(e)}, 500

api.add_resource(ClearSession, '/clear')
api.add_resource(IndexArticle, '/articles')
api.add_resource(ShowArticle, '/articles/<int:id>')
api.add_resource(Login, '/login')
api.add_resource(Logout, '/logout')
api.add_resource(CheckSession, '/check_session')
api.add_resource(SignUp, '/signup')
api.add_resource(CreateArticle, '/articles/create')
api.add_resource(GetArticle, '/my-articles')
api.add_resource(UploadImage, '/upload-image')

if __name__ == "__main__":
    app.run(port=5555, debug=True)