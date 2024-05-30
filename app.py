from flask import Flask, render_template, url_for, request, redirect, session, make_response, jsonify
import pymysql
import boto3 
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr
import secrets
import os
from botocore.exceptions import ClientError
import uuid
import logging
app = Flask(__name__)
app.config['SECRET_KEY'] = 'vYW1mik5y$ZKZX3?Iv08roh7gEc9F1yG'

aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
region_name = os.environ.get('AWS_REGION')

dynamodb = boto3.resource('dynamodb',aws_access_key_id=aws_access_key_id,
                          aws_secret_access_key=aws_secret_access_key,
                          region_name=region_name)

users_table = dynamodb.Table('users')
products_table = dynamodb.Table('product')
cart_table = dynamodb.Table('carts')
orders_table = dynamodb.Table('orders')


@app.route("/")
def index():
    products = products_table.scan()['Items']
    return render_template('index.html', products=products)

# Define route for login page
@app.route('/logincheck', methods=['GET', 'POST'])
def logincheck():

    username = request.form['uname']
    password = request.form['psw']

    response = users_table.query(
        IndexName='UsernameIndex',
        KeyConditionExpression=Key('username').eq(username),
        FilterExpression=Attr('password').eq(password)
    )

    user = response['Items'][0] if response['Items'] else None

    if user:
        products = products_table.scan()['Items']
        session['user'] = user['username']
        return render_template('index.html', products=products)
    else:
        return render_template('login.html', error=True)

    return render_template('login.html', error=False)

# Define route for login page
@app.route('/login', methods=['GET', 'POST'])
def login():
	return render_template('login.html', error=False)


@app.route('/add_to_cart', methods=['GET', 'POST'])
def add_to_cart():
    product_id = int(request.form['product_id'])
    quantity = int(request.form['quantity'])
    user_id = 0
    try:
        if session['user']:
            user_db = users_table.query(
                IndexName='UsernameIndex',
                KeyConditionExpression=Key('username').eq(session['user'])
            )['Items'][0]
            user_id = user_db['id']
    except:
        pass

    try:
        item = cart_table.get_item(Key={'product_id': product_id, 'user_id': user_id}).get('Item')
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            item = None
        else:
            raise

    if item:
        quantity_added = item['quantity'] + quantity
        cart_table.update_item(
            Key={'product_id': product_id, 'user_id': user_id},
            UpdateExpression='SET quantity = :q',
            ExpressionAttributeValues={':q': quantity_added}
        )
    else:
        cart_table.put_item(
            Item={
                'user_id': user_id,
                'product_id': product_id,
                'quantity': quantity
            }
        )
    products = products_table.scan()['Items']
    return render_template('index.html', products=products)

@app.route('/cart', methods=['GET', 'POST'])
def cart():

    user_id = 0
    try:
        if session['user']:
            user_db = users_table.query(
                IndexName='UsernameIndex',
                KeyConditionExpression=Key('username').eq(session['user'])
            )['Items'][0]
            user_id = user_db['id']
            print(f"user: {user_db}")
            logging.info(f"user: {user_db}")
    except:
        pass
    
    try:
        # Retrieve cart items from DynamoDB
        response = cart_table.query(
            KeyConditionExpression=Key('user_id').eq(user_id)
        )
        # cart_items = response['Items']
        cart_items = response.get('Items', [])
        logging.info(f"cart_items: {cart_items}")
    except:
        cart_items = []
    # Rearrange product data as a list of dictionaries
    product_list = []

    # Fetch product details for each cart item and calculate total price
    total_price = 0
    for item in cart_items:
        product_id = item['product_id']
        product = products_table.get_item(Key={'id': product_id}).get('Item')

        if product:
            product_dict = {
                'id': product['id'],
                'name': product['name'],
                'price': product['price'],
                'description': product['description'],
                'image_url': product['image_url'],
                'quantity': item['quantity'],
                'total_price': product['price'] * item['quantity']
            }
            product_list.append(product_dict)

    # Calculate the total price
    total = sum(prod['total_price'] for prod in product_list)
    # Render cart template with cart items
    return render_template('cart.html', cart_products=product_list, total_price=total)

@app.route('/update-cart-item/<int:product_id>', methods=['POST'])
def update_cart(product_id):
    quantity = int(request.json['quantity'])

    user_id = 0
    try:
        if session['user']:
            user_db = users_table.query(
                IndexName='UsernameIndex',
                KeyConditionExpression=Key('username').eq(session['user'])
            )['Items'][0]
            user_id = user_db['id']
    except:
        pass

    cart_table.update_item(
        Key={'product_id': product_id, 'user_id': user_id},
        UpdateExpression='SET quantity = :q',
        ExpressionAttributeValues={':q': quantity}
    )

    # Retrieve cart items from DynamoDB
    response = cart_table.query(
        KeyConditionExpression=Key('user_id').eq(user_id)
    )
    cart_items = response['Items']

    product_list = []
    total_price = 0
    for item in cart_items:
        product = products_table.get_item(Key={'id': item['product_id']}).get('Item')
        if product:
            product_dict = {}
            product_dict['id'] = product['id']
            product_dict['name'] = product['name']
            product_dict['price'] = product['price']
            product_dict['description'] = product['description']
            product_dict['image_url'] = product['image_url']
            product_dict['quantity'] = item['quantity']
            product_dict['total_price'] = product['price'] * item['quantity']
            product_list.append(product_dict)

    total = sum(prod['total_price'] for prod in product_list)

    return str(total)


@app.route('/delete-cart-item/<int:product_id>', methods=['POST'])
def delete_cart_item(product_id):
    user_id = 0
    try:
        if session['user']:
            user_db = users_table.query(
                IndexName='UsernameIndex',
                KeyConditionExpression=Key('username').eq(session['user'])
            )['Items'][0]
            user_id = user_db['id']
    except:
        pass

    response = cart_table.query(
        KeyConditionExpression=Key('user_id').eq(user_id)
    )
    cart_items = response['Items']
    print(f"pre delete: {cart_items}")
    
    # Delete the cart item from the cart_table in DynamoDB
    cart_table.delete_item(Key={'user_id': user_id, 'product_id': product_id})

    # Retrieve cart items from DynamoDB
    try:
        response = cart_table.query(
            KeyConditionExpression=Key('user_id').eq(user_id)
        )
        cart_items = response['Items']
    except:
        cart_items = []
    print(f"post delete: {cart_items}")
    # Rearrange product data as a list of dictionaries
    products = []
    total_price = 0

    for item in cart_items:
        product = products_table.get_item(Key={'id': item['product_id']}).get('Item')

        if product:
            product_dict = {
                'id': product['id'],
                'name': product['name'],
                'price': product['price'],
                'description': product['description'],
                'image_url': product['image_url'],
                'quantity': item['quantity'],
                'total_price': product['price'] * item['quantity']
            }
            products.append(product_dict)

    total = sum(prod['total_price'] for prod in products)

    return render_template('cart.html', cart_products=products, total_price=total)

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    user_id = 0
    try:
        if session['user']:
            user_db = users_table.query(
                IndexName='UsernameIndex',
                KeyConditionExpression=Key('username').eq(session['user'])
            )['Items'][0]
            user_id = user_db['id']
    except:
        pass

    if request.method == 'POST':
        # Retrieve cart items from DynamoDB
        try:
            response = cart_table.scan(
                FilterExpression=Attr('user_id').eq(user_id)
            )
            cart_items = response['Items']
        except:
            cart_items = []

        # Insert cart items into orders table and remove them from the cart
        for cart_item in cart_items:
            user_id = cart_item['user_id']
            product_id = cart_item['product_id']
            quantity = cart_item['quantity']

            orders_table.put_item(
                Item={
                    'id': int(uuid.uuid4().int % 1e9),
                    'user_id': user_id,
                    'product_id': product_id,
                    'quantity': quantity
                }
            )

            # Remove cart item from cart table
            cart_table.delete_item(Key={'user_id': user_id, 'product_id': product_id})
        """
        try:
            response = orders_table.scan(
                FilterExpression=Attr('user_id').eq(user_id)
            )
            orders_items = response['Items']
        except:
            orders_items = []
        """
        product_list = []
        total_price = 0

        for item in cart_items:
            product = products_table.get_item(Key={'id': item['product_id']}).get('Item')

            if product:
                product_dict = {
                    'id': product['id'],
                    'name': product['name'],
                    'price': product['price'],
                    'description': product['description'],
                    'image_url': product['image_url'],
                    'quantity': item['quantity'],
                    'total_price': product['price'] * item['quantity']
                }
                product_list.append(product_dict)

        total = sum(prod['total_price'] for prod in product_list)
        return render_template('orders.html', orders=product_list, total_price=total)
    else:
        # Retrieve cart items from DynamoDB
        try:
            response = cart_table.query(
                KeyConditionExpression=Key('user_id').eq(user_id)
            )
            cart_items = response['Items']
        except:
            cart_items = []

        product_list = []

        for item in cart_items:
            product = products_table.get_item(Key={'id': item['product_id']}).get('Item')

            if product:
                product_dict = {
                    'id': product['id'],
                    'name': product['name'],
                    'price': product['price'],
                    'description': product['description'],
                    'image_url': product['image_url'],
                    'quantity': item['quantity'],
                    'total_price': product['price'] * item['quantity']
                }
                product_list.append(product_dict)

        if cart_items==[]:
            total = 0
        else:
            total = sum(prod['total_price'] for prod in product_list)
        return render_template('checkout.html', cart_products=product_list, total_price=total)

@app.route('/aboutus')
def aboutus():
    # Display the contact details for the store
    return render_template('aboutus.html')

@app.route('/orders')
def orders():
    user_id = 0
    try:
        if session['user']:
            user_db = users_table.query(
                IndexName='UsernameIndex',
                KeyConditionExpression=Key('username').eq(session['user'])
            )['Items'][0]
            user_id = user_db['id']
    except:
        pass

    # Retrieve order items from DynamoDB
    try:
        response = orders_table.scan(
            FilterExpression=Attr('user_id').eq(user_id)
        )
    
        order_items = response['Items']
    except:
        order_items = []
    
    # Rearrange product data as a list of dictionaries
    product_list = []

    # Fetch product details for each order item and calculate total price
    total_price = 0
    for item in order_items:
        product = products_table.get_item(Key={'id': item['product_id']}).get('Item')
        if product:
            product_dict = {
                'id': product['id'],
                'name': product['name'],
                'price': product['price'],
                'description': product['description'],
                'image_url': product['image_url'],
                'quantity': item['quantity'],
                'total_price': product['price'] * item['quantity']
            }
            product_list.append(product_dict)

    # Render orders template with order items
    if order_items == []:
        total = total_price
    else:
        total = sum(prod['total_price'] for prod in product_list)

    return render_template('orders.html', orders=product_list, total_price=total)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Get form data
        username = request.form['username']
        password = request.form['password']

        # Check if user already exists in the database
        try:
            response = users_table.query(
                KeyConditionExpression=Key('username').eq(username)
            )
            if response['Items']:
                message = "User already exists"
                return render_template('register.html', message=message)
            else:
                # Add user to the database
                users_table.put_item(
                    Item={
                        'id': int(uuid.uuid4().int % 1e9),
                        'username': username,
                        'password': password
                    }
                )
                message = "Registration successful"
                return render_template('login.html', message=message)
        except:
            # Add user to the database
            users_table.put_item(
                Item={
                    'id': int(uuid.uuid4().int % 1e9),
                    'username': username,
                    'password': password
                }
            )
            message = "Registration successful"
            return render_template('login.html', message=message)

    return render_template('register.html')


@app.route("/logout")
def logout():
    session.pop("user", None)
    products = products_table.scan()['Items']
    return render_template('index.html', products=products)

@app.route('/contact')
def contact():
    return render_template('contact.html')