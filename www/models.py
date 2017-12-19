# @author shi.qi.chang
"""Model for users, quotes, comments."""
import uuid, time
from www.orm import Model, StringField, FloatField, BooleanField, TextField


def next_id():
    return '%015d%s000' % (int(time.time() * 1000), uuid.uuid4().hex)


class User(Model):
    __table__ = 'users'

    id = StringField(primary_key=True, default=next_id(), ddl='varchar(50)')
    name = StringField(ddl='varchar(50)')
    email = StringField(ddl='varchar(50)')
    passwd = StringField(ddl='varchar(50)')
    admin = BooleanField()
    image = StringField(ddl='varchar(500)')
    created_at = FloatField(default=time.time)


class Quote(Model):
    __table__ = 'quotes'

    id = StringField(primary_key=True, default=next_id(), ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    user_name = StringField(ddl='varchar(50)')
    user_image = StringField(ddl='varchar(500)')
    content = TextField()
    created_at = FloatField(default=time.time)


class Comment(Model):
    __table__ = 'comments'

    id = StringField(primary_key=True, default=next_id(), ddl='varchar(50)')
    quote_id = StringField(ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    user_name = StringField(ddl='varchar(50)')
    user_image = StringField(ddl='varchar(500)')
    content = TextField()
    created_at = FloatField(default=time.time)