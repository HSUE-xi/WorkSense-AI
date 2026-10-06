from flask import Flask
from routes.work_orders import work_orders_bp

app = Flask(__name__)

app.register_blueprint(work_orders_bp)


@app.route("/")
def home():
    return "Hello, WorkSense AI!"


if __name__ == "__main__":
    app.run(debug=True)