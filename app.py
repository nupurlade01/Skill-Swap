from flask import Flask, render_template, request, redirect, url_for
import mysql.connector
import bcrypt
import os

app = Flask(__name__)

# --- DATABASE CONFIGURATION ---
db_config = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'Swapnil@20'), 
    'database': os.getenv('DB_NAME', 'skillswap_db')
}

# Establish database connection
conn = None
cursor = None
try:
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    print("Database connection established successfully!")
except mysql.connector.Error as err:
    print(f"Database connection error: {err}")
# --- END OF CONFIGURATION ---

# Helper function to check connection status
def check_db_connection():
    """Returns True if the connection is alive, False otherwise."""
    return conn and conn.is_connected()

# --- Placeholder for Session Management ---
def get_current_user_id():
    # TEMPORARY: Hardcode User ID 13 for testing. This ID must exist!
    # In a real application, this would come from the user's session after login.
    return 13 
# --- END OF SESSION PLACEHOLDER ---


# --- CORE ROUTES ---

@app.route('/', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if not check_db_connection():
            return "Database connection is not available."

        name = request.form['name']
        skills = request.form['skills']
        purpose = request.form['purpose']
        contact = request.form['contact']
        profile_picture = request.form.get('profile_picture', '')
        
        # --- CAPTURE NEW FIELDS ---
        dob = request.form.get('dob') 
        age = request.form.get('age') 
        # ------------------------
        
        email = request.form['email']
        password = request.form['password']

        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            error_message = "Email already registered!"
            return render_template('form.html', error=error_message)

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        # --- UPDATED INSERT QUERY ---
        # NOTE: The database MUST have the 'dob' and 'age' columns added (via ALTER TABLE)
        query = """
            INSERT INTO users 
            (name, skills, purpose, contact, profile_picture, dob, age, email, password) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (name, skills, purpose, contact, profile_picture, dob, age, email, hashed_password)
        # ----------------------------
        
        try:
            cursor.execute(query, values)
            conn.commit()
        except mysql.connector.Error as err:
            print(f"Database insertion error: {err}")
            # Display a user-friendly error if the insertion fails (e.g., column mismatch)
            error_message = "A database error occurred during registration. Check server logs."
            return render_template('form.html', error=error_message)


        return redirect(url_for('landing'))

    return render_template('form.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error_message = None
    if request.method == 'POST':
        if not check_db_connection():
            return "Database connection is not available. Please check the server logs."

        email = request.form['email']
        password = request.form['password']

        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user:
            # user[7] is the password column in the users table
            if bcrypt.checkpw(password.encode('utf-8'), user[7].encode('utf-8')): 
                return redirect(url_for('landing'))
            else:
                error_message = "Login failed, check your email or password."
        else:
            error_message = "Login failed, check your email or password."

    return render_template('login.html', error_message=error_message)

@app.route('/landing', methods=['GET'])
def landing():
    if not check_db_connection():
        return "Database connection is not available. Please check the server logs."

    query = request.args.get('query', '').strip()
    filters = request.args.getlist('filter') 
    
    # Select all fields required by landing.html
    sql_query = "SELECT id, name, skills, purpose, contact, profile_picture, email FROM users"
    params = []
    conditions = []

    if query:
        conditions.append(" (LOWER(TRIM(name)) LIKE LOWER(%s) OR LOWER(TRIM(skills)) LIKE LOWER(%s) OR LOWER(TRIM(purpose)) LIKE LOWER(%s)) ")
        search_term = '%' + query + '%'
        params.extend([search_term, search_term, search_term])
    
    if filters:
        filter_conditions = ["LOWER(purpose) LIKE %s"] * len(filters)
        conditions.append("(" + " OR ".join(filter_conditions) + ")") 
        params.extend(['%' + f.lower() + '%' for f in filters])

    if conditions:
        sql_query += " WHERE " + " AND ".join(conditions)

    cursor.execute(sql_query, tuple(params))
    user_data = cursor.fetchall()

    return render_template('landing.html', users=user_data)


# ----------------------------------------------------------------------
# 🌟 NEW ROUTE TO HANDLE SENDING MESSAGES 🌟
# ----------------------------------------------------------------------
@app.route('/send_message', methods=['POST'])
def send_message():
    if not check_db_connection():
        return "Database connection is not available."

    # Sender is the currently logged-in user (hardcoded for testing)
    sender_id = get_current_user_id() 
    
    try:
        # Get recipient ID and message body from the AJAX request/form data
        recipient_id = request.form['recipient_id']
        message_body = request.form['message_body']

        if not recipient_id or not message_body:
            print("Error: Missing recipient_id or message_body.")
            return 'Error: Missing data', 400

        # Prevent user from messaging themselves (optional check)
        if sender_id == int(recipient_id):
            print("Error: Cannot send message to self.")
            return 'Error: Cannot message self', 400
            
        # SQL INSERT Query
        query = """
            INSERT INTO messages (sender_id, recipient_id, message_body, is_read) 
            VALUES (%s, %s, %s, FALSE)
        """
        values = (sender_id, recipient_id, message_body)
        cursor.execute(query, values)
        conn.commit()
        
        # In a production app, you might return JSON success: {'status': 'success'}
        return 'Message sent successfully!', 200
        
    except mysql.connector.Error as err:
        print("\n--- MESSAGE INSERTION FAILED ---")
        print(f"ERROR: {err}")
        print("--------------------------------\n")
        return 'Database error during message insertion', 500
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return 'Server error', 500


# --- OTHER ROUTES (Collaboration, Notifications, etc.) ---

@app.route('/collaborate', methods=['GET'])
def collaborate():
    if not check_db_connection():
        return "Database connection is not available. Please check the server logs."
    
    try:
        # Fetch requests including the poster's name using a JOIN
        cursor.execute("""
            SELECT 
                pr.title, pr.description, pr.skill_needed, pr.created_at, u.name as poster_name
            FROM projects_requests pr
            JOIN users u ON pr.poster_id = u.id
            ORDER BY pr.created_at DESC
        """)
        requests_feed = cursor.fetchall()
    except mysql.connector.Error as err:
        print(f"Error fetching requests for display: {err}")
        requests_feed = []

    return render_template('collaborate.html', requests=requests_feed)


@app.route('/post_request', methods=['POST'])
def post_request():
    if not check_db_connection():
        return "Database connection is not available. Please check the server logs."

    # Use a valid, existing user ID (e.g., 1)
    poster_id = get_current_user_id() 
    
    try:
        title = request.form['title']
        description = request.form['description']
        skill_needed = request.form['skill_needed']

        # Ensure all columns are included in the INSERT statement
        query = """
            INSERT INTO projects_requests (poster_id, title, description, skill_needed) 
            VALUES (%s, %s, %s, %s)
        """
        values = (poster_id, title, description, skill_needed)
        cursor.execute(query, values)
        conn.commit()
        
    except mysql.connector.Error as err:
        print("\n--- DATABASE INSERTION FAILED ---")
        print(f"ERROR: {err}")
        print(f"Query: {query}")
        print(f"Values: {values}")
        print("--------------------------------\n")
        return redirect(url_for('collaborate'))

    return redirect(url_for('collaborate'))


@app.route('/notifications', methods=['GET'])
def notifications_feed():
    user_id = get_current_user_id() 
    
    if not check_db_connection():
        return "Database connection is not available."

    try:
        # notification[0]=message, notification[1]=created_at, notification[2]=is_read
        cursor.execute("SELECT message, created_at, is_read FROM notifications WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
        notification_feed = cursor.fetchall()
        
        # Mark notifications as read
        cursor.execute("UPDATE notifications SET is_read = TRUE WHERE user_id = %s AND is_read = FALSE", (user_id,))
        conn.commit()

    except mysql.connector.Error as err:
        print(f"Error fetching notifications: {err}")
        notification_feed = []

    return render_template('notifications.html', notifications=notification_feed)

@app.route('/code_board')
def code_board():
    return render_template('code_board.html')

@app.route('/skill_swap')
def skill_swap():
    # To properly implement the skill_swap page with real data
    # you would need to query the database here.
    return render_template('skill_swap.html')

@app.route('/users')
def users():
    if not check_db_connection():
        return "Database connection is not available. Please check the server logs."

    cursor.execute("SELECT id, name, skills, purpose, contact, profile_picture, email FROM users")
    user_data = cursor.fetchall()
    return render_template('users.html', users=user_data)

@app.route('/detailed_users', methods=['GET'])
def detailed_users_report():
    if not check_db_connection():
        return "Database connection is not available."
    try:
        # This executes the Correlated Subquery
        cursor.execute("""
            SELECT u1.name, LENGTH(u1.skills) AS Skill_Length, DATE(u1.registration_date) AS Registration_Day
            FROM users u1
            WHERE LENGTH(u1.skills) > (SELECT AVG(LENGTH(u2.skills)) FROM users u2 WHERE DATE(u2.registration_date) = DATE(u1.registration_date))
            ORDER BY Skill_Length DESC;
        """)
        detailed_users = cursor.fetchall()
    except mysql.connector.Error as err:
        print(f"Error running correlated subquery: {err}")
        detailed_users = []
    return render_template('detailed_users.html', detailed_users=detailed_users)


# ----------------------------------------------------------------------
# 🌟 NEW ROUTE TO DISPLAY MUTUAL MESSAGING REPORT 🌟
# ----------------------------------------------------------------------
@app.route('/mutual_messages')
def mutual_messages_report():
    if not check_db_connection():
        return "Database connection is not available."
    
    try:
        # Query to find users who have sent messages to each other (mutual messaging)
        query = """
            SELECT
                m1.sender_id,
                sender1.name AS User1_Name,
                m1.recipient_id,
                recipient1.name AS User2_Name,
                COUNT(*) AS Messages_Between_Them
            FROM
                messages m1
            INNER JOIN
                messages m2 ON m1.sender_id = m2.recipient_id 
                            AND m1.recipient_id = m2.sender_id
            INNER JOIN
                users sender1 ON m1.sender_id = sender1.id
            INNER JOIN
                users recipient1 ON m1.recipient_id = recipient1.id
            WHERE
                m1.sender_id < m1.recipient_id
            GROUP BY
                m1.sender_id, m1.recipient_id, sender1.name, recipient1.name;
        """
        cursor.execute(query)
        mutual_data = cursor.fetchall()
        
    except mysql.connector.Error as err:
        print(f"Error running mutual messages query: {err}")
        mutual_data = []
        
    return render_template('mutual_messages.html', mutual_messages=mutual_data)


if __name__ == '__main__':
    app.run(debug=True)