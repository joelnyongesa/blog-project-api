from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData
from sqlalchemy_serializer import SerializerMixin
from sqlalchemy.ext.hybrid import hybrid_property
from flask_bcrypt import Bcrypt
from sqlalchemy import Enum

metadata = MetaData(naming_convention={
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
})

db = SQLAlchemy(metadata=metadata)
bcrypt = Bcrypt()

class Article(db.Model, SerializerMixin):
    __tablename__ = 'articles'

    serialize_rules = ('-user.articles',)

    DEFAULT_PREVIEW_IMAGE = "https://res.cloudinary.com/df3n8xhsq/image/upload/v1744458196/341-800x450_zeafvw.jpg"


    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String)
    title = db.Column(db.String)
    content = db.Column(db.String)
    preview_text = db.Column(db.String)
    preview_image = db.Column(db.String, default=DEFAULT_PREVIEW_IMAGE)
    minutes_to_read = db.Column(db.Integer)
    tag = db.Column(Enum('Product', 'Engineering', 'Design', name='tag_enum'), default='Engineering', nullable=False)
    date = db.Column(db.DateTime, server_default=db.func.now())

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    def __repr__(self):
        return f'Article {self.id} by {self.author}'

class User(db.Model, SerializerMixin):
    __tablename__ = 'users'

    serialize_rules = ('-articles.user',)

    DEFAULT_AVATAR = "https://res.cloudinary.com/df3n8xhsq/image/upload/w_1000,c_fill,ar_1:1,g_auto,r_max,bo_5px_solid_red,b_rgb:262c35/v1744403231/bear_hh1n40.png"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, unique=True)
    _password_hash = db.Column(db.String)
    avatar = db.Column(db.String, default=DEFAULT_AVATAR)

    articles = db.relationship('Article', backref='user')

    @hybrid_property
    def password_hash(self):
        raise AttributeError('Password hash cannot be viewed')
    
    @password_hash.setter
    def password_hash(self, password):
        password_hash = bcrypt.generate_password_hash(password)
        self._password_hash = password_hash.decode('utf-8')

    def authenticate(self, password):
        return bcrypt.check_password_hash(self._password_hash, password)