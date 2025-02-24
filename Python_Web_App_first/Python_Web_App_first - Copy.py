from flask import Flask, render_template, request, redirect, url_for, flash
from flask_mysqldb import MySQL
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Apply ProxyFix middleware
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

# MySQL configurations
app.config['MYSQL_HOST'] = '192.168.0.35'
app.config['MYSQL_USER'] = 'PYTHON'
app.config['MYSQL_PASSWORD'] = 'python'
app.config['MYSQL_DB'] = 'atlasshop'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

PermissionsDB = {
    'host': '192.168.0.35',
    'user': 'PYTHON',
    'password': 'python',
    'database': 'atlasdb',
}

class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

@login_manager.user_loader
def load_user(user_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    if user:
        return User(user['id'], user['username'], user['password'])
    return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        if user and check_password_hash(user['password'], password):
            login_user(User(user['id'], user['username'], user['password']))
            flash('Logged in successfully.')
            return redirect(url_for('shop'))
        else:
            flash('Invalid credentials.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('home'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_password))
        mysql.connection.commit()
        cur.close()
        flash('You have successfully registered! Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/servers')
def servers():
    return render_template('servers.html')

@app.route('/menu')
def menu():
    return render_template('menu.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/shop', methods=['GET', 'POST'])
@login_required
def shop():
    if request.method == 'POST':
        steam_id = request.form['steam_id']
        points = int(request.form['points'])
        amount_spent = calculate_amount_spent(points)
        add_points_to_user(steam_id, points)
        insert_purchase_record(steam_id, points, amount_spent)
        flash(f'Successfully added {points} points to Steam ID {steam_id} for ${amount_spent}!')
        return redirect(url_for('shop'))
    return render_template('shop.html')

def calculate_amount_spent(points):
    return points / 100  # Assuming $10 per 1000 points

def add_points_to_user(steam_id, points):
    try:
        cur = mysql.connection.cursor()
        cur.execute("UPDATE players SET Points = Points + %s WHERE SteamId = %s", (points, steam_id))
        mysql.connection.commit()
        cur.close()
    except MySQLdb.OperationalError as e:
        print(f"OperationalError: {e}")
        cur.close()

def insert_purchase_record(steam_id, points, amount_spent):
    try:
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO purchase_records (steam_id, points, amount_spent) VALUES (%s, %s, %s)", (steam_id, points, amount_spent))
        mysql.connection.commit()
        cur.close()
    except MySQLdb.OperationalError as e:
        print(f"OperationalError: {e}")
        cur.close()

@app.route('/records', methods=['GET'])
@login_required
def records():
    try:
        cur = mysql.connection.cursor()
        steam_id = request.args.get('steam_id')
        sort_order = request.args.get('sort', 'asc')  # Default sort order is ascending
        
        if steam_id:
            cur.execute("SELECT steam_id, points, amount_spent, purchase_date FROM purchase_records WHERE steam_id = %s ORDER BY purchase_date " + sort_order, (steam_id,))
        else:
            cur.execute("SELECT steam_id, points, amount_spent, purchase_date FROM purchase_records ORDER BY purchase_date " + sort_order)
        
        records = cur.fetchall()
        total_amount_spent = sum(record['amount_spent'] for record in records)
        cur.close()
        return render_template('records.html', records=records, total_amount_spent=total_amount_spent, sort_order=sort_order)
    except MySQLdb.OperationalError as e:
        print(f"OperationalError: {e}")
        return render_template('records.html', records=[], total_amount_spent=0)

# Helper function to get a connection to the second database
def get_atlasdb_connection():
    return pymysql.connect(
        host=PermissionsDB['host'],
        user=PermissionsDB['user'],
        password=PermissionsDB['password'],
        database=PermissionsDB['database'],
        cursorclass=pymysql.cursors.DictCursor,
    )

@app.route('/permissions')
def permissions():
    search_term = request.args.get('search', '').lower()  # Get search term, default to empty string
    try:
        # Connect to the atlasdb database
        connection = get_atlasdb_connection()
        with connection.cursor() as cursor:
            if search_term:
                # Search by Steam ID or Permission Group
                cursor.execute("""
                    SELECT * FROM players 
                    WHERE LOWER(SteamId) LIKE %s OR LOWER(PermissionGroups) LIKE %s
                """, (f"%{search_term}%", f"%{search_term}%"))
            else:
                # No search term, return all records
                cursor.execute("SELECT * FROM players")
            permissions = cursor.fetchall()
        return render_template('permissions.html', permissions=permissions)
    except Exception as e:
        print(f"Error: {e}")
        return "Error fetching permissions from the database.", 500
    finally:
        connection.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)

