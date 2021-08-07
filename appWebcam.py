import functools
from flask import Flask, render_template, session, request, \
	copy_current_request_context, Response, redirect, url_for, abort
from engineio.payload import Payload
from flask_login import LoginManager, UserMixin, \
								login_required, login_user, logout_user, current_user 
from mjpeg.client import MJPEGClient
from mjpeg.server import MJPEGResponse
import base64
url='http://192.168.1.69/webcam/?action=stream'

# Create a new client thread
client = MJPEGClient(url)

# Allocate memory buffers for frames
bufs = client.request_buffers(65536, 50)
for b in bufs:
    client.enqueue_buffer(b)
    
# Start the client in a background thread
client.start()
#https://flask-socketio.readthedocs.io/en/latest/
# Set this variable to "threading", "eventlet" or "gevent" to test the
# different async modes, or leave it set to None for the application to choose
# the best option based on installed packages.
# virtualenv -p python3 venv
# . venv/bin/activate
# pip install -r requirements.txt
# python app.py
async_mode = None
Payload.max_decode_packets = 500
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
# flask-login
login_manager = LoginManager()
login_manager.init_app(app)


# silly user model
class User(UserMixin):

	def __init__(self, id):
		self.id = id
		self.name = "user" + str(id)
		self.password = self.name + "_secret"
		
	def __repr__(self):
		return "%d/%s/%s" % (self.id, self.name, self.password)

def relay():
	while True:
		buf = client.dequeue_buffer()
		yield memoryview(buf.data)[:buf.used]
		client.enqueue_buffer(buf)
		
@app.route('/')
@login_required
def index():
	return MJPEGResponse(relay())

# handle login failed
@app.errorhandler(401)
def page_not_found(e):
	return redirect("/login")
	
	
# callback to reload the user object		
@login_manager.user_loader
def load_user(userid):
	return User(userid)

if __name__ == '__main__':
	app.run(port=5001, host="0.0.0.0")
