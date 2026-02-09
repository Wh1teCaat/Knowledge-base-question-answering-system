import logging
import grpc
import os
import asyncio
import sys
from pathlib import Path
from typing import AsyncIterator

proto_dir = str(Path(__file__).parent / "proto")
sys.path.insert(0, proto_dir)
import agent_pb2, agent_pb2_grpc
from agent import Agent, Receipt

class AgentServiceServicer(agent_pb2_grpc.AgentServiceServicer):
    def __init__(self, agent: Agent):
        self.agent = agent
        logging.info("AgentServiceServicer initialized with Agent instance.")

    async def Chat(
        self, 
        request_iterator: AsyncIterator[agent_pb2.ChatReq],
        context: grpc.aio.ServicerContext
    ) -> AsyncIterator[agent_pb2.ChatResp]:
        """
        双向流式 RPC 方法，处理来自客户端的聊天请求并返回响应。
        """
        metadata = dict(context.invocation_metadata())
        user_id = metadata.get("user_id", "unknown")

        try:
            async for chat_req in request_iterator:
                logging.info(f"Received chat request from user_id={user_id}: {chat_req.query}")

                try:
                    # 调用 agent 处理
                    response = await self.agent.ainvoke(
                        query=chat_req.query,
                        thread_id=chat_req.thread_id,
                    )

                    if type(response) == Receipt:
                        answer = response.answer
                    else:
                        answer = str(response)

                    chat_resp = agent_pb2.ChatResp(response=answer)
                    yield chat_resp
                except Exception as e:
                    logging.error(f"Error processing request from user_id={user_id}: {e}")
                    await context.abort(grpc.StatusCode.INTERNAL, f"Error processing request: {str(e)}")
        except Exception as e:
            logging.error(f"Stream error: {e}")
            await context.abort(grpc.StatusCode.INTERNAL, f"Stream error: {str(e)}")

async def serve(host: str = "[::]:50052", max_workers: int = 100):
    """
    启动 gRPC 服务器，注册 AgentService
    """

    logging.info("Initializing Agent instance...")
    agent = await Agent.create()
    logging.info("Agent instance created.")

    # 创建服务器实例
    server = grpc.aio.server(
        options=[
        ("grpc.max_send_message_length", 100 * 1024 * 1024),  # 100 MB
        ("grpc.max_receive_message_length", 100 * 1024 * 1024),  # 100 MB
        ("grpc.max_concurrent_streams", max_workers),
        ("grpc.http2.max_pings_without_data", 0),  # 允许无限制的 ping
        ]
    )

    agent_pb2_grpc.add_AgentServiceServicer_to_server(
        AgentServiceServicer(agent),
        server,
    )

    server.add_insecure_port(host)
    logging.info(f"Starting gRPC server on {host}...")
    await server.start()
    logging.info("gRPC server started.")

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logging.info("Shutting down gRPC server...")
        await server.stop(5)
        await agent.aclose()
        logging.info("Server stopped.")

if __name__ == "__main__":
    os.environ["USER_AGENT"] = "grpc-agent-server/1.0"
    asyncio.run(serve())