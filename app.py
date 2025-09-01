import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from config import Config
import cloudinary
import cloudinary.uploader
import cloudinary.api

# --- Inizializzazione Applicazione e Database ---

app = Flask(__name__)
app.config.from_object(Config)

# Configure Cloudinary
if app.config.get('CLOUDINARY_URL'):
    cloudinary.config(cloudinary_url=app.config['CLOUDINARY_URL'])

db = SQLAlchemy(app)

# --- Modelli del Database (usando SQLAlchemy) ---

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    position = db.Column(db.Integer)
    products = db.relationship('Product', backref='category', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Category {self.name}>'

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    price = db.Column(db.Float, default=0.0)
    description = db.Column(db.Text)
    size = db.Column(db.String(50))
    color = db.Column(db.String(50))
    consumo = db.Column(db.String(100))
    tessuto = db.Column(db.String(100))
    accessori = db.Column(db.String(200))
    image_filenames = db.Column(db.String(1000)) # Now stores Cloudinary Public IDs

    def __repr__(self):
        return f'<Product {self.name}>'

# --- Route dell'Applicazione ---

@app.context_processor
def inject_cloudinary_helpers():
    """Injects Cloudinary URL generation utility into templates."""
    def get_cloudinary_url(public_id, **options):
        if cloudinary.config().cloud_name:
            return cloudinary.utils.cloudinary_url(public_id, **options)[0]
        return "" # Return empty string or a placeholder if not configured
    return dict(cloudinary_url=get_cloudinary_url)

@app.route('/')
def index():
    """Homepage: mostra le categorie e permette la ricerca di articoli."""
    query = request.args.get('q')
    if query:
        products = Product.query.filter(or_(Product.name.ilike(f'%{query}%'), Product.description.ilike(f'%{query}%'))).all()
    else:
        products = []
    
    total_products_count = Product.query.count()

    from sqlalchemy import func
    category_product_counts = db.session.query(
        Category.id,
        func.count(Product.id)
    ).outerjoin(Product).group_by(Category.id).all()

    category_counts_map = {cat_id: count for cat_id, count in category_product_counts}

    categories = Category.query.order_by(Category.position).all()
    
    for category in categories:
        category.product_count = category_counts_map.get(category.id, 0)

    return render_template('index.html', categories=categories, products=products, query=query, total_products_count=total_products_count)

@app.route('/api/search')
def api_search():
    """Fornisce suggerimenti per la ricerca di articoli in formato JSON."""
    query = request.args.get('q', '')
    if not query or len(query) < 2:
        return jsonify([])

    products = Product.query.filter(Product.name.ilike(f'%{query}%')).limit(10).all()
    suggestions = [product.name for product in products]
    return jsonify(suggestions)

@app.route('/category/<int:category_id>')
def category(category_id):
    """Pagina di una categoria: mostra gli articoli e permette la ricerca."""
    current_category = Category.query.get_or_404(category_id)
    query = request.args.get('q')
    
    products_query = Product.query.filter_by(category_id=category_id)
    if query:
        products_query = products_query.filter(or_(Product.name.ilike(f'%{query}%'), Product.description.ilike(f'%{query}%')))
    
    products = products_query.order_by(Product.name).all()
    category_products_count = Product.query.filter_by(category_id=category_id).count()

    return render_template('category.html', products=products, category=current_category, query=query, category_products_count=category_products_count)

@app.route('/product/<int:product_id>')
def product(product_id):
    """Pagina di dettaglio dell'articolo."""
    product_item = Product.query.get_or_404(product_id)
    public_ids = product_item.image_filenames.split(',') if product_item.image_filenames else []
    return render_template('product.html', product=product_item, public_ids=public_ids)

@app.route('/add', methods=['GET', 'POST'])
def add_product():
    """Pagina per aggiungere un nuovo articolo."""
    if request.method == 'POST':
        name = request.form.get('name')
        category_id = request.form.get('category_id')
        price = request.form.get('price') or 0.0
        description = request.form.get('description')
        size = request.form.get('size') or 'Non specificato'
        color = request.form.get('color') or 'Non specificato'
        consumo = request.form.get('consumo')
        tessuto = request.form.get('tessuto')
        accessori = request.form.get('accessori')

        if not category_id:
            flash('Categoria è un campo obbligatorio!', 'danger')
            categories = Category.query.order_by(Category.name).all()
            return render_template('add_product.html', categories=categories)

        # Cloudinary Upload Logic
        uploaded_files = request.files.getlist('images')
        public_ids = []
        for file in uploaded_files:
            if file:
                try:
                    upload_result = cloudinary.uploader.upload(file, folder="APPAmore_uploads")
                    public_ids.append(upload_result['public_id'])
                except Exception as e:
                    flash(f'Image upload failed: {e}', 'danger')
                    categories = Category.query.order_by(Category.name).all()
                    return render_template('add_product.html', categories=categories)
        
        image_public_ids_str = ','.join(public_ids)

        new_product = Product(
            name=name, category_id=category_id, price=price, description=description,
            size=size, color=color, consumo=consumo, tessuto=tessuto, accessori=accessori,
            image_filenames=image_public_ids_str
        )
        db.session.add(new_product)
        db.session.commit()
        
        flash('Articolo aggiunto con successo!', 'success')
        return redirect(url_for('index'))

    categories = Category.query.order_by(Category.name).all()
    return render_template('add_product.html', categories=categories)

@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    # NOTE: This function does not yet handle updating/deleting existing images.
    product_to_edit = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        product_to_edit.name = request.form.get('name')
        product_to_edit.category_id = request.form.get('category_id')
        product_to_edit.price = request.form.get('price') or 0.0
        product_to_edit.description = request.form.get('description')
        product_to_edit.size = request.form.get('size') or 'Non specificato'
        product_to_edit.color = request.form.get('color') or 'Non specificato'
        product_to_edit.consumo = request.form.get('consumo')
        product_to_edit.tessuto = request.form.get('tessuto')
        product_to_edit.accessori = request.form.get('accessori')
        
        db.session.commit()
        flash('Articolo aggiornato con successo!', 'success')
        return redirect(url_for('product', product_id=product_to_edit.id))

    categories = Category.query.order_by(Category.name).all()
    return render_template('edit_product.html', product=product_to_edit, categories=categories)

@app.route('/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    """Elimina un articolo dal database e da Cloudinary."""
    product_to_delete = Product.query.get_or_404(product_id)
    
    if product_to_delete.image_filenames:
        public_ids = product_to_delete.image_filenames.split(',')
        for public_id in public_ids:
            if public_id:
                try:
                    cloudinary.uploader.destroy(public_id)
                except Exception as e:
                    print(f"Error deleting image {public_id} from Cloudinary: {e}")

    db.session.delete(product_to_delete)
    db.session.commit()
    flash('Articolo eliminato con successo!', 'success')
    return redirect(url_for('index'))

@app.route('/add_category', methods=['GET', 'POST'])
def add_category():
    if request.method == 'POST':
        category_name = request.form.get('name')
        if category_name:
            existing_category = Category.query.filter_by(name=category_name).first()
            if existing_category:
                flash('Una categoria con questo nome esiste già.', 'danger')
                return render_template('add_category.html')

            max_pos = db.session.query(db.func.max(Category.position)).scalar()
            new_pos = max_pos + 1 if max_pos is not None else 0
            new_category = Category(name=category_name, position=new_pos)
            db.session.add(new_category)
            db.session.commit()
            flash('Categoria aggiunta con successo!', 'success')
            return redirect(url_for('index'))
    return render_template('add_category.html')

@app.route('/delete_category/<int:category_id>', methods=['POST'])
def delete_category(category_id):
    category_to_delete = Category.query.get_or_404(category_id)
    db.session.delete(category_to_delete)
    db.session.commit()
    flash('Categoria eliminata con successo!', 'success')
    return redirect(url_for('index'))

@app.route('/category/<int:category_id>/move/<direction>')
def move_category(category_id, direction):
    cat_to_move = Category.query.get_or_404(category_id)
    
    if direction == 'up':
        prev_cat = Category.query.filter(Category.position < cat_to_move.position).order_by(Category.position.desc()).first()
        if prev_cat:
            cat_to_move.position, prev_cat.position = prev_cat.position, cat_to_move.position
            db.session.commit()
    elif direction == 'down':
        next_cat = Category.query.filter(Category.position > cat_to_move.position).order_by(Category.position.asc()).first()
        if next_cat:
            cat_to_move.position, next_cat.position = next_cat.position, cat_to_move.position
            db.session.commit()
            
    return redirect(url_for('index'))

# --- Comandi CLI per la gestione del DB ---

@app.cli.command("init-db")
def init_db_command():
    """Crea le tabelle del database."""
    with app.app_context():
        db.create_all()
        print("Database inizializzato.")

@app.cli.command("migrate-db")
def migrate_db_command():
    """Aggiunge la colonna 'position' e la popola."""
    from sqlalchemy import inspect, text
    with app.app_context():
        inspector = inspect(db.engine)
        if 'categories' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('categories')]
            if 'position' not in columns:
                db.session.execute(text('ALTER TABLE categories ADD COLUMN position INTEGER;'))
                db.session.commit()
                print("Colonna 'position' aggiunta alla tabella 'categories'.")

            categories = Category.query.order_by(Category.name).all()
            for i, category in enumerate(categories):
                if category.position is None:
                    category.position = i
            db.session.commit()
            print("Valori di 'position' popolati per le categorie esistenti.")
        else:
            print("Tabella 'categories' non trovata.")

@app.cli.command("migrate-product-attributes")
def migrate_product_attributes_command():
    """Aggiunge le nuove colonne alla tabella products."""
    from sqlalchemy import inspect, text
    with app.app_context():
        inspector = inspect(db.engine)
        if 'products' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('products')]
            new_cols = {'consumo': 'VARCHAR(100)', 'tessuto': 'VARCHAR(100)', 'accessori': 'VARCHAR(200)'}
            for col, col_type in new_cols.items():
                if col not in columns:
                    db.session.execute(text(f'ALTER TABLE products ADD COLUMN {col} {col_type};'))
                    print(f"Colonna '{col}' aggiunta alla tabella 'products'.")
            db.session.commit()
        else:
            print("Tabella 'products' non trovata.")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)