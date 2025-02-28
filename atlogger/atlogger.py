import requests
import time
import websockets
import datetime
import json

# disable HAS_IPV6
requests.packages.urllib3.util.connection.HAS_IPV6 = False # noqa



# Trace class to hold trace data
class Trace:
    data: dict

    def __init__(self, function_name: str, function_args: dict | None = None):
        if function_args is None:
            function_args = {}

        self.data = {
            "function_name": function_name,
            "function_args": function_args,
            "time_start": time.time(),
            "events": [{
                "name": "start",
                "time_delta_ms": 0
            }]
        }
    
    def add_event(self, event_name: str, event_data: dict | None = None):
        t = time.time()

        t_delta = t - self.data["time_start"]
        event_time = int(t_delta * 1000)
        
        event = {
            "name": event_name,
            "time_delta_ms": event_time,
            "type": "event"
        }
        if event_data:
            event["data"] = event_data
        self.data["events"].append(event)
    
    def add_trace(self, trace: "Trace"):
        # add another trace as an event
        t = time.time()
        t_delta = t - self.data["time_start"]
        event_time = int(t_delta * 1000)

        event = {
            "name": trace.data["function_name"],
            "time_delta_ms": event_time,
            "trace": trace.to_json(),
            "type": "trace"
        }
        self.data["events"].append(event)
    
    @staticmethod
    def from_json(data: dict) -> "Trace":
        trace = Trace(data["function_name"], data["function_args"])
        trace.data = data
        return trace
    

    def to_json(self):
        return self.data
    
    def pretty_print(self):
        start_time = datetime.datetime.fromtimestamp(self.data["time_start"])
        print(f"Trace for {self.data['function_name']} at {start_time}")
        print(f"Arguments: {self.data['function_args']}")
        print("Events:")
        for event in self.data["events"]:
            print("|")
            print(f"|- {event['time_delta_ms']}ms: {event['name']}")
            if event.get("data"):
                print(f"|  | {event['data']}")
            if event.get("trace"):
                print(f"|  | Trace: {event['trace']}")
        
        print("End of trace")

class ATLogger:
    def __init__(self, host_url: str, token: str):
        self.host_url = host_url
        self.__token = token

        self.headers = {
            "Authorization": f"Bearer {self.__token}",
            "Content-Type": "application/json"
        }

        self.session = requests.Session()

    def new_trace(self, function_name: str, function_args: dict | None = None) -> Trace:
        if function_args is None:
            function_args = {}
            
        return Trace(function_name, function_args)
    
    def submit_trace(self, trace: Trace):
        response = self.session.post(f"{self.host_url}/api/v1/submit_trace", json=trace.to_json(), headers=self.headers)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Error submitting trace: {response.status_code} - {response.text}")


class ATLoggerWS:
    def __init__(self, host_url: str, token: str):
        # Convert HTTP URL to WebSocket URL if necessary
        if host_url.startswith("http://"):
            self.host_url = host_url.replace("http://", "ws://")
        elif host_url.startswith("https://"):
            self.host_url = host_url.replace("https://", "wss://")
        else:
            self.host_url = host_url
        
        self.token = token
        self.websocket = None
        self.connected = False

    async def connect(self):
        """Establish WebSocket connection"""
        if self.websocket is None or not self.connected:
            self.websocket = await websockets.connect(
                f"{self.host_url}/ws/v1/trace?token={self.token}"
            )
            self.connected = True
        return self.websocket

    def new_trace(self, function_name: str, function_args: dict | None = None) -> Trace:
        """Create a new trace - same as HTTP version"""
        if function_args is None:
            function_args = {}
            
        return Trace(function_name, function_args)
    
    async def submit_trace(self, trace: Trace):
        """Submit trace via WebSocket"""
        if not self.connected:
            await self.connect()
        
        try:
            await self.websocket.send(json.dumps(trace.to_json()))
            response = await self.websocket.recv()
            return json.loads(response)
        except Exception as e:
            # If connection is lost, try to reconnect once
            if not self.connected:
                await self.connect()
                await self.websocket.send(json.dumps(trace.to_json()))
                response = await self.websocket.recv()
                return json.loads(response)
            else:
                raise Exception(f"Error submitting trace via WebSocket: {str(e)}")
    
    async def close(self):
        """Close the WebSocket connection"""
        if self.websocket and self.connected:
            await self.websocket.close()
            self.connected = False