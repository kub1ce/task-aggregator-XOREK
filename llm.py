import asyncio
import aiohttp
from typing import AsyncGenerator
import sys, json

class ChatFacade:
    def __init__(self, client):
        self.client = client
        self.request_response_service = RequestResponseService(client)
        self.console_service = ConsoleService()
        self.exit_ai = "/exitAI"
    
    async def run(self):
        while True:
            query_message = self.console_service.get_query_from_console()
            
            if query_message == self.exit_ai:
                break
            
            response = self.request_response_service.get_message_response_stream(query_message)
            
            await self.console_service.print_response_to_console_async(response)

class RequestResponseService:
    def __init__(self, client):
        self.client = client
    
    def get_message_response_stream(self, query_message: str) -> AsyncGenerator[str, None]:
        return self.client.get_streaming_response(query_message)

class ConsoleService:
    def get_query_from_console(self) -> str:
        while True:
            sys.stdout.write("Напиши запрос к ИИ: ")
            sys.stdout.flush()
            query_string = sys.stdin.readline().strip()
            if query_string:
                return query_string
    
    async def print_response_to_console_async(self, response: AsyncGenerator[str, None]):
        async for item in response:
            sys.stdout.write(json.loads(item)["response"])
            sys.stdout.flush()
        sys.stdout.write('\n')

class OllamaChatClient:
    def __init__(self, base_url: str, model_name: str):
        self.base_url = base_url
        self.model_name = model_name
    
    async def get_streaming_response(self, query_message: str):
        # Имитация вызова Ollama API с потоковым ответом
        url = f"{self.base_url}/api/generate"
        
        data = {
            "model": self.model_name,
            "prompt": query_message,
            "stream": True
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    if response.status == 200:
                        # Имитация потокового ответа
                        async for line in response.content:
                            if line:
                                yield line.decode('utf-8')
                    else:
                        yield f"Ошибка: {response.status}"
        except Exception as e:
            yield f"Ошибка подключения: {str(e)}"

async def main():
    try:
        client = OllamaChatClient("http://localhost:11434", "qwen3-coder:30b")
        
        facade = ChatFacade(client)
        await facade.run()
        
    except Exception as exception:
        print(f"Ошибка: {str(exception)}")

if __name__ == "__main__":
    asyncio.run(main())
