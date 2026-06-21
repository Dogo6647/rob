    if message.content.startswith("#!eval") and str(message.author.id) == str(OWNER_ID):
        code = message.content.replace("#!eval ", "")
        print(f":: [SECURITY WARNING] - executing eval '{code}'.")
        buffer = io.StringIO()

        try:
            with redirect_stdout(buffer):
                exec(code)

            output = buffer.getvalue() or "(no output)"
            await message.channel.send(f"```\n{output}\n```")
        except Exception as e:
            await message.channel.send(f"```\n{type(e).__name__}: {e}\n```")
