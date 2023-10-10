# Twitch Drops Watchdog

Want to be notified whenever a new Twitch drop campaign starts? This bot will send you an email whenever it finds a new drop campaign for the games that you specify. [Subscribe here](https://twitch-drops-bot.uw.r.appspot.com/).


## Host it Yourself

https://support.google.com/accounts/answer/185833?hl=en#zippy=%2Cwhy-you-may-need-an-app-password

### Sample Config

```json
{
    "notifications": {
        "email": {
            "credentials": {
                "user": "my-from-email@example.com",
                "password": "my-email-password"
            },
            "subscribers": [
                {
                    "events": {
                        "new_drop_campaign": {
                            "games": [
                                "rocket league",
                                "overwatch 2"
                            ]
                        },
                        "new_game": {}
                    },
                    "timezone": "utc",
                    "recipients": [
                        "apricot@example.com",
                        "blueberry@example.com",
                        "coconut@example.com"
                    ]
                }
            ]
        },
        "discord": {
            "subscribers": [
                {
                    "timezone": "utc",
                    "events": {
                        "new_drop_campaign": {},
                        "new_game": {}
                    },
                    "webhook_urls": [
                        "https://discord.com/api/webhooks/123/abc",
                        "https://discord.com/api/webhooks/456/def"
                    ]
                },
                {
                    "timezone": "utc",
                    "events": {
                        "new_drop_campaign": {
                            "games": [
                                "apex legends"
                            ]
                        },
                        "new_game": {}
                    },
                    "webhook_urls": [
                        "https://discord.com/api/webhooks/789/ghi"
                    ]
                }
            ]
        }
    }
}
```