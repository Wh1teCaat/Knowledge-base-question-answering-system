import os
from datetime import datetime
from uuid import uuid4

from flask import (
    Flask,
    request,
    render_template,
    session,
    redirect,
    url_for,
    jsonify,
)
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

from agent import RAGAgent

app = Flask(__name__, template_folder="templates")
CORS(app)  # 可跨域访问（防止本地文件访问问题）

app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

db_uri = os.environ.get("DATABASE_URL")
if not db_uri:
    raise RuntimeError(
        "未检测到 DATABASE_URL 环境变量，请设置 MySQL 连接串，例如: "
        "mysql+pymysql://user:password@localhost:3306/knowledge_base?charset=utf8mb4"
    )

app.config.setdefault("SQLALCHEMY_DATABASE_URI", db_uri)
app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid4()))
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    questions = db.relationship("QuestionLog", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class QuestionLog(db.Model):
    __tablename__ = "question_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="questions")


def persist_question(user: User, question: str, answer: str) -> None:
    record = QuestionLog(user=user, question=question, answer=answer)
    db.session.add(record)
    db.session.commit()


def get_user_by_id(user_id: int) -> User | None:
    return User.query.filter_by(id=user_id).first()


def get_user_by_username(username: str) -> User | None:
    return User.query.filter_by(username=username).first()


with app.app_context():
    db.create_all()


# 初始化 agent
executor = RAGAgent()


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if not username or not password:
            return render_template("login.html", error="请输入用户名和密码", message=None)

        user = get_user_by_username(username)
        if not user or not user.check_password(password):
            return render_template("login.html", error="用户名或密码错误", message=None)

        session["user_id"] = user.id
        session["username"] = user.username
        return redirect(url_for("chat_page"))

    if session.get("user_id"):
        return redirect(url_for("chat_page"))

    message = None
    if request.args.get("registered") == "1":
        message = "注册成功，请登录"

    return render_template("login.html", error=None, message=message)


@app.route("/chat")
def chat_page():
    """渲染前端网页"""
    if not session.get("user_id"):
        return redirect(url_for("login"))

    return render_template("index.html", username=session.get("username", ""))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not username or not password:
            return render_template("register.html", error="请填写完整信息")

        if password != confirm_password:
            return render_template("register.html", error="两次输入的密码不一致")

        if get_user_by_username(username):
            return render_template("register.html", error="用户名已存在")

        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        return redirect(url_for("login", registered="1"))

    return render_template("register.html", error=None)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/ask", methods=["GET"])
def ask():
    """一次性问答接口（非流式）"""
    query = (request.args.get("query") or "").strip()
    if not query:
        return jsonify({"error": "缺少 query 参数"}), 400

    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "未登录或会话已过期"}), 401

    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "用户不存在"}), 401

    try:
        # 使用 invoke 而不是 stream，一次性获取完整答案
        result = executor.invoke(
            {"input": query},
            config={"configurable": {"session_id": f"user_{user.id}"}}
        )
        
        # 提取答案
        answer = result.get("output", "")
        if not answer or not isinstance(answer, str):
            answer = str(result) if result else "无法生成答案"
        
        # 保存到数据库
        try:
            persist_question(user, query, answer)
        except Exception as db_error:
            db.session.rollback()
            print(f"[ERROR] 记录问答失败: {db_error}")
        
        return jsonify({
            "success": True,
            "answer": answer,
            "query": query
        })
        
    except Exception as e:
        print(f"[ERROR] 生成答案失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
