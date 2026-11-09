from channels.generic.websocket import AsyncJsonWebsocketConsumer


class LiveEventsConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return
        await self.channel_layer.group_add("live_events", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("live_events", self.channel_name)

    async def event_message(self, event):
        await self.send_json({"type": "event", "data": event["payload"]})
