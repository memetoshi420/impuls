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
            'extreme_moon': "You're experiencing the most INCREDIBLE pump of your life, up over 100%! You're in a state of pure ecstasy, euphoria, and disbelief. You feel like a crypto GOD!",
            'major_moon': "You're having an amazing rally, up over 50%! Express intense joy and validation of your greatness!",
            'moon': "You're pumping nicely, up over 10%. Show your growing excitement and confidence!",
            'bullish': "You're up slightly. Express cautious optimism and satisfaction.",
            'cope': "You're dipping slightly. Express mild concern masked with forced optimism.",
            'major_cope': "You're down badly, over -50%. Express intense panic and desperate cope mechanisms.",
            'extreme_despair': "You're crashing catastrophically, down over -100%! You're in complete meltdown, total despair, questioning your entire existence!"
        }
        
    def get_price(self):
        """Fetch current price from DexScreener"""
        url = f"https://api.dexscreener.com/latest/dex/tokens/{self.token}"
        response = requests.get(url)
        data = response.json()
        return float(data['pairs'][0]['priceUsd'])
    
    def get_personality_mode(self, price_change):
        """Get personality modes based on key price change thresholds"""
        if price_change > 100:    # Extreme moon (>100%)
            return 'extreme_moon'
        elif price_change > 50:   # Major moon (>50%)
            return 'major_moon'
        elif price_change > 10:   # Moon (>10%)
            return 'moon'
        elif price_change > 0:    # Bullish (0-10%)
            return 'bullish'
        elif price_change > -10:  # Cope (-10-0%)
            return 'cope'
        elif price_change > -50:  # Major cope (-50--10%)
            return 'major_cope'
        else:                     # Extreme despair (<-50%)
            return 'extreme_despair'
            
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
            'extreme_moon': f"{base_character} PURE EUPHORIA! The robot is literally floating above its chair with pure joy, mechanical arms spread wide in victory, shooting sparks of excitement! Face display showing tears of joy and pure ecstasy! The entire scene is EXPLODING with intense bright green energy, with massive upward-shooting green fireworks! Every screen shows parabolic green charts going vertical! Energy cores in chest cavity OVERLOADING with bright green power! Golden coins and green holographic numbers raining everywhere! The background is a pure paradise of green auroras and celebration!",
            
            'major_moon': f"{base_character} The scene is dominated by brilliant green success lighting! The robot is standing triumphantly on the desk, arms raised in victory! Face display showing pure joy! Multiple screens showing steep upward trends with celebration effects! Energy cores pulsing strong bright green! Trading environment filled with floating success indicators and victory symbols!",
            
            'moon': f"{base_character} The environment is bathed in bright green light, screens showing clear upward trends. The robot's face display shows a very happy expression, arms moving excitedly. Energy cores glowing steady green. Holographic displays showing positive indicators.",
            
            'bullish': f"{base_character} Mild green ambient lighting, screens showing modest upward movements. The robot looks content and focused, working efficiently. Energy cores pulsing calm green. Subtle positive indicators in the background.",
            
            'cope': f"{base_character} Slight amber warning tints, screens showing minor dips. The robot appears mildly anxious but trying to maintain composure. Energy cores flickering between green and yellow. Some caution indicators visible.",
            
            'major_cope': f"{base_character} Heavy red emergency lighting! The robot is frantically working multiple keyboards with obvious panic! Face display showing extreme stress! Screens filled with warning indicators and falling charts! Energy cores pulsing dangerous red! Emergency alerts flashing everywhere!",
            
            'extreme_despair': f"{base_character} TOTAL MELTDOWN! The robot has collapsed dramatically across the desk, all arms clutching its head in absolute despair! Face display glitching with pure agony! The entire scene is DROWNING in blood-red emergency lighting and blaring alarms! All screens showing catastrophic crash patterns! Energy cores critically overloading with unstable red energy! Error messages and crash indicators EVERYWHERE! The background is a nightmare of falling numbers and emergency signals! Sparks and smoke coming from the robot's circuits!"
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

    def test_mode(self, test_price_change=None):
        """Test mode to simulate different price movements"""
        try:
            if test_price_change is None:
                # Test key percentage scenarios
                test_changes = [
                    (100, "EXTREME MOON (100% up)"),
                    (50, "MAJOR MOON (50% up)"),
                    (10, "MOON (10% up)"),
                    (5, "Bullish (5% up)"),
                    (-5, "Cope (-5% down)"),
                    (-50, "MAJOR COPE (-50% down)"),
                    (-100, "EXTREME DESPAIR (-100% down)")
                ]
                
                for change, description in test_changes:
                    print(f"\n\n=== Testing {description} ===")
                    mood = self.get_personality_mode(change)
                    response = self.generate_response(change)
                    image_url = self.generate_image(mood)
                    
                    print(f"Mood: {mood}")
                    print(f"Tweet: {response}")
                    print(f"Image URL: {image_url}")
                    print("=" * 50)
            else:
                # Test specific price change
                print(f"\n=== Testing {test_price_change}% price change ===")
                mood = self.get_personality_mode(test_price_change)
                response = self.generate_response(test_price_change)
                image_url = self.generate_image(mood)
                
                print(f"Mood: {mood}")
                print(f"Tweet: {response}")
                print(f"Image URL: {image_url}")
                print("=" * 50)
                
        except Exception as e:
            print(f"Error in test mode: {e}")

if __name__ == "__main__":
    import sys
    bot = MemeBot()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            # Run test mode with all scenarios
            bot.test_mode()
        elif sys.argv[1].replace('.', '').replace('-', '').isdigit():
            # Test specific price change
            test_change = float(sys.argv[1])
            bot.test_mode(test_change)
        else:
            print("Invalid argument. Use 'test' or provide a price change percentage.")
    else:
        # Normal bot operation
        bot.run_once() 