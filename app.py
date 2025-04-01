import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, request, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import case
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import gc

app = Flask(__name__)

gc.collect()

app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///default.db'
app.config['SQLALCHEMY_BINDS'] = {
    'users': 'sqlite:///users.db',
    'reviews': 'sqlite:///reviews.db',
}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class Review(db.Model):
    __bind_key__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)    
    anime_id = db.Column(db.Integer, nullable=False)
    username = db.Column(db.String(150), nullable=False)
    content =  db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class User(db.Model, UserMixin):
    __bind_key__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username and password: 
            user = user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password, password):
                login_user(user)
                flash('Logged in successfully')
                return redirect(url_for('index'))
            else:
                flash('Invalid username and password')
        else:
            flash('Username and password are required')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('index'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Password does not match')
            return redirect(url_for('register'))

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists.')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password)

        db.session.add(new_user)
        db.session.commit()
        flash('Signup successful! Please log in.')
        return redirect(url_for('login'))
    return render_template('signup.html')


@app.route('/')
@app.route('/index.html')
def index():
    return render_template('index.html')

@app.route('/categories.html')
def categories():
    return render_template('categories.html')


file_path = 'CS_IA_Anime_Spreadsheet.csv'
data = pd.read_csv(file_path)

genre_file_map = {
    "slice of life": "sliceoflife",
    "sci-fi": "scifi",
    "time travel": "timetravel",
    "gag humor": "gaghumor"
}

def genreSearch(genre):
    results = []
    target_genre = genre
    genre_columns = data.columns[2:8]

    # Iterate over each row and check if the input genre is present
    for index, row in data.iterrows():
        anime_title = row[0]
        id = str(row[12])
        episodes = row[10]

        # Collect genres with original capitalization for display and lowercase for comparison
        genres_display = [row[genre] for genre in genre_columns if pd.notnull(row[genre])]
        genres_lower = [genre.lower() for genre in genres_display]
        
        # Check if input genre is in the list of lowercase genres
        if target_genre in genres_lower:
            results.append({'title': anime_title, 'genres': ', '.join(genres_display), 'id': id, 'episodes': episodes})
    
    return results

@app.route('/genres/<genre>.html')
def genrePage(genre):
    genre_key = genre.replace(" ", "").lower()
    genre_name = next((key for key, value in genre_file_map.items() if value == genre_key), genre)

    results = genreSearch(genre_name)
    return render_template(f'genres/{genre}.html', results=results)

@app.route('/anime<id>.html')
def animePage(id):
    anime = data[data['ID'] == int(id)].squeeze()  # Find the anime by ID

    if anime.empty:
        return "Anime not found", 404
    
    genre_columns = data.columns[2:8]
    genres_display = [anime[genre] for genre in genre_columns if pd.notnull(anime[genre])]
    anime_genres = ', '.join(genres_display)

    special_user = "Creator"
    reviews = Review.query.filter_by(anime_id=id).order_by(
        case((Review.username == special_user, 1), else_=0).desc(),
        Review.timestamp.desc()
    ).all()

    return render_template('anime.html', anime=anime, genres=anime_genres, reviews=reviews, special_user = special_user)

@app.route('/anime/review/<int:id>', methods=['POST'])
@login_required
def write_review(id):
    review_text = request.form.get('review')
    username = current_user.username

    new_review = Review(anime_id=id, username=username, content=review_text)
    db.session.add(new_review)
    db.session.commit()

    flash('Your review has been submitted')
    return redirect(url_for('animePage', id=id))

@app.route('/anime/review/delete/<int:review_id>', methods=['POST'])
@login_required
def delete_review(review_id):
    review = Review.query.get_or_404(review_id)

    # Check if the current user is the author of the review
    if review.username != current_user.username:
        flash("You are not authorized to delete this review.")
        return redirect(url_for('anime_page', id=review.anime_id))

    # Delete the review
    db.session.delete(review)
    db.session.commit()

    flash('Review has been deleted successfully!')
    return redirect(url_for('animePage', id=review.anime_id))


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1')
    
