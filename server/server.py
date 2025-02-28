#log-everything/server/server.py

from fastapi import FastAPI, HTTPException, Header, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse
import uvicorn
import sys
import json
from typing import Optional, List
import os
import uuid
import json

from atlogger.atlogger import Trace


os.chdir(os.path.dirname(os.path.abspath(__file__)))
print(os.getcwd())


if os.path.exists(".token"):
    with open(".token", "r") as file:
        API_TOKEN = file.read().strip()
else:
    API_TOKEN = str(uuid.uuid4())

    with open(".token", "w") as file:
        file.write(API_TOKEN)
    
    print(f"Generated new API token: {API_TOKEN}")


app = FastAPI()

def save_trace(trace_data: dict):
    function_name = trace_data["function_name"]
    time_start = trace_data["time_start"]
    trace = Trace.from_json(trace_data)

    if not os.path.exists(f"./traces/{function_name}"):
        os.makedirs(f"./traces/{function_name}", exist_ok=True)
    
    trace_file = f"./traces/{function_name}/{time_start}.json"
    with open(trace_file, "w") as file:
        json.dump(trace.to_json(), file, indent=4)

@app.post("/api/v1/submit_trace")
async def submit_trace(trace: dict, authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    token_type, token = authorization.split()
    if token_type != "Bearer" or token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    save_trace(trace)    

    return JSONResponse(content={"status": "success"})

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

manager = ConnectionManager()

@app.websocket("/ws/v1/trace")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    # Authenticate the WebSocket connection
    if token != API_TOKEN:
        await websocket.close(code=1008, reason="Invalid authentication token")
        return
    
    await manager.connect(websocket)
    try:
        while True:
            # Receive trace data
            data_text = await websocket.receive_text()
            trace = json.loads(data_text)
            
            # Save the trace
            save_trace(trace)
            
            # Send response back to client
            await websocket.send_text(json.dumps({"status": "success"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        await websocket.close(code=1011, reason=f"Internal server error: {str(e)}")
        manager.disconnect(websocket)


if __name__ == "__main__":
    port = 8000 if len(sys.argv) < 2 else int(sys.argv[1])
    uvicorn.run(app, host="0.0.0.0", port=port)