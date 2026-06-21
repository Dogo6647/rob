    import requests
    if message.content.startswith("#!dadjoke") and message.guild:
        try:
            data = requests.get("https://icanhazdadjoke.com/", headers={"Accept": "application/json"})
            joke = data.json().get('joke')
            history.append({"role": "assistant", "content": joke})
            await message.channel.send(f"{joke}")
        except Exception as e:
            await message.channel.send(f"sorry, cant fetch a dad joke rn ):")
            await message.channel.send(f"you can try later tho :3")
