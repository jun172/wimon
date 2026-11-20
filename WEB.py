from AUTH import AUTH
from C1 import c1_bp
from C2 import c2_bp
from CSRF import CSRF
from DARK import DARK
from DT import DT
from FU import FU
from ONE import ONE
from SQL import SQL
from brute import brute_bp
from ddos import stress_bp

# ⬅️ 追加: 脅迫文モック＆ログ管理用Blueprintのインポート
from dark_logger import dark_logger_bp
from flask import Flask, render_template
from gobuster import gobuster_bp
from IP import ip_bp, log_access
from nc import nc_bp
from nmap import namp
from XSS import XSS
from index import index_bp 

app = Flask(__name__)
app.secret_key = "jun.1026"
app.after_request(log_access)


@app.route("/")
def home():
  return render_template("home.html")


# 脆弱性学習用Blueprint登録
app.register_blueprint(SQL, url_prefix="/SQL")
app.register_blueprint(XSS, url_prefix="/XSS")
app.register_blueprint(CSRF, url_prefix="/CSRF")
app.register_blueprint(DT, url_prefix="/DT")
app.register_blueprint(ONE, url_prefix="/ONE")
app.register_blueprint(FU, url_prefix="/FU")
app.register_blueprint(DARK, url_prefix="/DARK")
app.register_blueprint(AUTH, url_prefix="/AUTH")
app.register_blueprint(brute_bp, url_prefix="/brute")

# ネットワーク・セキュリティ実験用Blueprint登録 (CyberLab)
app.register_blueprint(namp, url_prefix="/namp")
app.register_blueprint(nc_bp, url_prefix="/nc")
app.register_blueprint(stress_bp, url_prefix="/ddos")
app.register_blueprint(c2_bp, url_prefix="/c2")
app.register_blueprint(c1_bp, url_prefix="/c1")
app.register_blueprint(ip_bp, url_prefix="/ip")
app.register_blueprint(gobuster_bp, url_prefix="/gobuster")
app.register_blueprint(dark_logger_bp, url_prefix="/portal")
app.register_blueprint(index_bp, url_prefix="/index")

if __name__ == "__main__":
  app.run(
      host="0.0.0.0",
      port=8081,
      debug=False,
  )