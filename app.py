from threading import Lock
import functools
from flask import Flask, render_template, session, request, \
	copy_current_request_context, Response, redirect, url_for, abort
from flask_socketio import SocketIO, emit, join_room, leave_room, \
	close_room, rooms, disconnect
from engineio.payload import Payload
from flask_login import LoginManager, UserMixin, \
								login_required, login_user, logout_user, current_user 

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
#pip install eventlet
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*", logger=True, engineio_logger=True)
# socketio = SocketIO(app, async_mode='gevent')
thread = None
thread_lock = Lock()
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
	
def background_thread():
	"""Example of how to send server generated events to clients."""
	count = 0
	while True:
		socketio.sleep(10)
		count += 1
		socketio.emit('my_response',
					  {'data': 'Server generated event', 'count': count})


@app.route('/')
@login_required
def index():
	return render_template('index.html', async_mode=socketio.async_mode)

# somewhere to login
@app.route("/login", methods=["GET", "POST"])
def login():
	if request.method == 'POST':
		username = request.form['username']
		password = request.form['password']		
		if password == username + "_secret":
			id = username.split('user')[1]
			user = User(id)
			login_user(user)
			return redirect("/")
		else:
			return abort(401)
	else:
		return Response('''
		<form action="" method="post">
			<p><input type=text name=username>
			<p><input type=password name=password>
			<p><input type=submit value=Login>
		</form>
		''')


# somewhere to logout
@app.route("/logout")
@login_required
def logout():
	logout_user()
	return Response('<p>Logged out</p>')


# handle login failed
@app.errorhandler(401)
def page_not_found(e):
	return redirect("/login")
	
	
# callback to reload the user object		
@login_manager.user_loader
def load_user(userid):
	return User(userid)

@socketio.on('connect')
def connect_handler():
	if current_user.is_authenticated:
		emit('my response',
			 {'message': '{0} has joined'.format(current_user.name)},
			 broadcast=True)
	else:
		return False  # not allowed here	
		
def authenticated_only(f):
	@functools.wraps(f)
	def wrapped(*args, **kwargs):
		if not current_user.is_authenticated:
			disconnect()
		else:
			return f(*args, **kwargs)
	return wrapped
	
@socketio.event
@authenticated_only
def my_event(message):
	print('message ', message)
	session['receive_count'] = session.get('receive_count', 0) + 1
	emit('my_response',
		 {'data': "pouet pouet " + message['data'], 'count': session['receive_count']})


@socketio.event
@authenticated_only
def my_broadcast_event(message):
	session['receive_count'] = session.get('receive_count', 0) + 1
	emit('my_response',
		 {'data': message['data'], 'count': session['receive_count']},
		 broadcast=True)


@socketio.event
@authenticated_only
def join(message):
	join_room(message['room'])
	session['receive_count'] = session.get('receive_count', 0) + 1
	emit('my_response',
		 {'data': 'In rooms: ' + ', '.join(rooms()),
		  'count': session['receive_count']})


@socketio.event
@authenticated_only
def leave(message):
	leave_room(message['room'])
	session['receive_count'] = session.get('receive_count', 0) + 1
	emit('my_response',
		 {'data': 'In rooms: ' + ', '.join(rooms()),
		  'count': session['receive_count']})


@socketio.on('close_room')
@authenticated_only
def on_close_room(message):
	session['receive_count'] = session.get('receive_count', 0) + 1
	emit('my_response', {'data': 'Room ' + message['room'] + ' is closing.',
						 'count': session['receive_count']},
		 to=message['room'])
	close_room(message['room'])


@socketio.event
@authenticated_only
def my_room_event(message):
	session['receive_count'] = session.get('receive_count', 0) + 1
	emit('my_response',
		 {'data': message['data'], 'count': session['receive_count']},
		 to=message['room'])


@socketio.event
def disconnect_request():
	@copy_current_request_context
	def can_disconnect():
		disconnect()

	session['receive_count'] = session.get('receive_count', 0) + 1
	# for this emit we use a callback function
	# when the callback function is invoked we know that the message has been
	# received and it is safe to disconnect
	emit('my_response',
		 {'data': 'Disconnected!', 'count': session['receive_count']},
		 callback=can_disconnect)


@socketio.event
def my_ping():
	emit('my_pong')


@socketio.event
def connect():
	if current_user.is_authenticated == False:
		return False
	else:
		global thread
		with thread_lock:
			if thread is None:
				thread = socketio.start_background_task(background_thread)
		emit('my_response', {'data': 'Connected', 'count': 0})


@socketio.on('disconnect')
def test_disconnect():
	print('Client disconnected', request.sid)


if __name__ == '__main__':
	socketio.run(app, port=5000, host="0.0.0.0")
