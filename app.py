from agent import RAGAgent
from flask import Flask, request, jsonify

app = Flask(__name__)

# 初始化agent
executor = RAGAgent().get_memory_runnable()


@app.route("/")
def home():
    return "应用启动"


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    query = data.get("query", "").strip()

    if not query:
        return jsonify({"error": "请输入问题"}), 400

    response_docs = executor.invoke({"input": query},
                                    config={"configurable": {"session_id": "user_a"}})
    answer = "\n".join([doc.page_content for doc in response_docs])
    return jsonify({"query": query, "answer": answer})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
