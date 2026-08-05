    if message.content.startswith("#!quota"):
        def progress_bar(remaining, total, length=24):
            if remaining is None or total is None or total == 0:
                return "[unknown]"

            used = total - remaining
            ratio = used / total
            filled = round(ratio * length)

            return "█" * filled + "░" * (length - filled)

        tmp_request = await generate_response(prompt="", history=[])
        tmp_request = None

        req_limit = int(rate_limit["limit_requests"])
        tok_limit = int(rate_limit["limit_tokens"])
        req_used = int(rate_limit["remaining_requests"])
        req_left = req_limit - req_used
        tok_used = int(rate_limit["remaining_tokens"])
        tok_left = tok_limit - tok_used

        text = (
            f"requests per day\n"
            f"`{progress_bar(req_left, req_limit)}`\n"
            f"{req_used}/{req_limit} used ({req_left} remaining)\n\n"

            f"tokens per minute\n"
            f"`{progress_bar(tok_left, tok_limit)}`\n"
            f"{tok_used}/{tok_limit} used ({tok_left} remaining)"
        )

        if (
            (req_left == 0 or tok_left == 0)
            and rate_limit["retry_after"] is not None
        ):
            text += f"\n\nim tired rn.\nmsg me after **{rate_limit['retry_after']} seconds**."

        await message.channel.send(text)
        return
