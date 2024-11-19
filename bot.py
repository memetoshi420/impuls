import os
import requests
import time
from openai import OpenAI
from dotenv import load_dotenv
from collections import deque
from datetime import datetime
import tweepy
import base64

class MemeBot:
    def __init__(self):
        load_dotenv()
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.token = "AVyjco9j8vv7ZPkhCpEoPJ3bLEuw7G1wrrNt8DrApump"
        self.token_symbol = "$IMPULS"
        self.price_history = deque(maxlen=5)
        
        # Base character prompt for consistency
        self.base_prompt = """A hyperrealistic 3D octane render of a part-human, part-cyborg character sitting at a chaotic trading desk. 
        The character has exaggerated, stressed features such as large glowing red eyes and a metallic robotic arm with sparks and wires exposed. 
        The desk is cluttered with glowing monitors displaying volatile market charts, with sharp green candles and crashing red lines. 
        Dollar signs and currency symbols float above the character's head, symbolizing obsession with trading. 
        The background is illuminated with cyberpunk neon lights, featuring a mix of industrial and futuristic aesthetics. 
        Scattered around the desk are dollar bills, coins, and crumpled papers. 
        The character has a humorous, frantic expression, emphasizing the theme of emotional, impulsive trading. 
        The scene is colorful, detailed, and playful, combining a chaotic trading environment with cyberpunk elements."""
        
        # Twitter API Auth
        self.twitter_client = tweepy.Client(
            consumer_key=os.getenv("TWITTER_API_KEY"),
            consumer_secret=os.getenv("TWITTER_API_SECRET"),
            access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
            access_token_secret=os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
        )
        
        # Need v1 auth for media upload
        self.twitter_auth = tweepy.OAuth1UserHandler(
            os.getenv("TWITTER_API_KEY"),
            os.getenv("TWITTER_API_SECRET"),
            os.getenv("TWITTER_ACCESS_TOKEN"),
            os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
        )
        self.twitter_api = tweepy.API(self.twitter_auth)
        
        self.personality_modes = {
            'moon': "You're absolutely mooning right now. Express pure euphoria and confidence.",
            'bullish': "You're climbing steadily. Express growing confidence and validation.",
            'cope': "You're dipping but in denial. Express defensive optimism.",
            'despair': "You're dumping hard. Express dramatic despair and existential crisis."
        }
        
    def get_price(self):
        """Fetch current price from DexScreener"""
        url = f"https://api.dexscreener.com/latest/dex/tokens/{self.token}"
        response = requests.get(url)
        data = response.json()
        return float(data['pairs'][0]['priceUsd'])
    
    def get_personality_mode(self, price_change):
        if price_change > 10:
            return 'moon'
        elif price_change > 0:
            return 'bullish'
        elif price_change > -10:
            return 'cope'
        else:
            return 'despair'
            
    def generate_response(self, price_change):
        """Generate response based on price movement"""
        mode = self.get_personality_mode(price_change)
        prompt = f"""
        {self.base_prompt}

        Current situation: {self.personality_modes[mode]}
        
        Generate a single tweet as $IMPULS expressing your current emotional state.
        Remember: 
        - No emojis
        - No price numbers
        - No quotation marks
        - Pure emotional reaction only
        - Never use quotes in the response
        """
            
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[{
                "role": "system",
                "content": "You are $IMPULS, an AI token. Always respond in character. Never use quotation marks in your response."
            },
            {
                "role": "user",
                "content": prompt
            }],
            max_tokens=100,
            temperature=0.9
        )
        
        # Strip any quotes from the response
        tweet_text = response.choices[0].message.content.strip().strip('"\'')
        return tweet_text

    def generate_image_prompt(self, mood):
        """Generate DALL-E prompt based on mood"""
        base_character = """A sleek, genderless robotic trading entity with a metallic chrome finish, digital display screen for a face showing expressions, multiple mechanical arms with exposed circuitry, sitting at a futuristic trading station. The robot has a clear transparent chest cavity showing pulsing circuits and energy cores."""
        
        mood_prompts = {
            'moon': f"{base_character} The scene is DOMINATED by intense neon green lighting and multiple holographic displays showing MASSIVE upward price charts with giant green arrows pointing up. The robot's face display shows pure ecstasy, arms raised in triumph, digital eyes glowing bright green. Energy cores in chest pulsing bright green. Trading desk surrounded by floating holographic green candles and upward trending charts. Background filled with raining digital green numbers.",
            
            'bullish': f"{base_character} The environment is bathed in bright green light, multiple screens showing clear upward trending charts with prominent green arrows. The robot's face display shows a confident expression, mechanical arms moving energetically across keyboards. Energy cores glowing steady green. Holographic displays all around showing positive green indicators and rising trends.",
            
            'cope': f"{base_character} The scene is tinted with anxious amber warning lights, screens showing wavering charts with small red dips. The robot's face display shows nervous static, one arm clutching its head dramatically. Energy cores flickering between yellow and red. Multiple warning indicators and red exclamation marks floating in the background. Scattered emergency lights casting nervous shadows.",
            
            'despair': f"{base_character} The entire scene is FLOODED with harsh emergency red lighting and alarms. All screens showing CATASTROPHIC downward crashes with huge red arrows pointing down. The robot's face display shows pure agony, multiple arms clutching its head in despair. Energy cores pulsing dangerous red. Trading desk covered in error messages and crash indicators. Background filled with falling digital red numbers and downward trending charts."
        }
        return mood_prompts[mood]

    def generate_image(self, mood):
        """Generate image using DALL-E"""
        try:
            prompt = self.generate_image_prompt(mood)
            response = self.client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            
            image_url = response.data[0].url
            print(f"Image generated successfully: {image_url}")
            return image_url
            
        except Exception as e:
            print(f"Error generating image: {e}")
            return None

    def post_tweet(self, tweet_text, image_url):
        """Post tweet with image"""
        try:
            # Download image
            image_response = requests.get(image_url)
            if image_response.status_code != 200:
                raise Exception("Failed to download image")

            # Save image temporarily
            temp_image = "temp_mood.png"
            with open(temp_image, "wb") as f:
                f.write(image_response.content)

            # Upload media to Twitter
            media = self.twitter_api.media_upload(filename=temp_image)
            
            # Post tweet with media
            self.twitter_client.create_tweet(
                text=tweet_text,
                media_ids=[media.media_id]
            )
            
            # Clean up temp file
            os.remove(temp_image)
            
            print("Tweet posted successfully with image!")
            return True
            
        except Exception as e:
            print(f"Error posting tweet: {e}")
            return False

    def run_once(self):
        """Single price check and response"""
        try:
            current_price = self.get_price()
            
            if self.price_history:
                last_price = self.price_history[-1][0]
                price_change = ((current_price - last_price) / last_price) * 100
            else:
                price_change = 1.0
                
            print(f"\nCurrent price: ${current_price:.6f}")
            mood = self.get_personality_mode(price_change)
            response = self.generate_response(price_change)
            image_url = self.generate_image(mood)
            
            print(f"\nMode: {mood}")
            print(f"Response: {response}")
            print(f"Image URL: {image_url}")
            
            self.post_tweet(response, image_url)
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    bot = MemeBot()
    bot.run_once() 