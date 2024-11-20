import os
import time
import requests
import asyncio
import websockets
import json
from openai import OpenAI
from dotenv import load_dotenv
from collections import deque
from datetime import datetime
import tweepy

class PriceTracker:
    """Base class for price tracking"""
    def __init__(self, token, check_interval):
        self.token = token
        self.check_interval = check_interval
        self.last_price = None
        self.last_check_time = None
        
    async def get_price(self):
        """Must be implemented by child classes"""
        raise NotImplementedError

class PumpFunTracker(PriceTracker):
    """Phase 1: PumpFun price tracking via WebSocket"""
    def __init__(self, token):
        super().__init__(token, check_interval=300)  # 5 minutes
        self.websocket = None
        self.last_market_cap = None
        
    async def connect(self):
        """Establish WebSocket connection"""
        try:
            uri = "wss://pumpportal.fun/api/data"
            print("Attempting WebSocket connection...")
            self.websocket = await websockets.connect(uri)
            
            payload = {
                "method": "subscribeTokenTrade",
                "keys": [self.token]
            }
            print("Sending subscription payload...")
            await self.websocket.send(json.dumps(payload))
            
            # Skip subscription confirmation
            print("Waiting for subscription confirmation...")
            confirmation = await self.websocket.recv()
            print(f"Subscription response: {confirmation}")
            
            print("Connected and subscribed to PumpPortal WebSocket")
            return True
            
        except Exception as e:
            print(f"WebSocket connection error: {e}")
            self.websocket = None
            return False
            
    async def get_price(self):
        """Get price from PumpFun"""
        try:
            if not self.websocket:
                if not await self.connect():
                    print("Failed to connect to WebSocket")
                    return None, None
                    
            print("Waiting for trade data...")
            message = await self.websocket.recv()
            data = json.loads(message)
            print(f"Received trade data: {data}")
            
            if 'marketCapSol' in data:
                market_cap_sol = float(data['marketCapSol'])
                
                # Calculate price change from market cap
                if self.last_market_cap:
                    market_cap_change = ((market_cap_sol - self.last_market_cap) / self.last_market_cap) * 100
                else:
                    market_cap_change = 0
                    
                self.last_market_cap = market_cap_sol
                self.last_check_time = time.time()
                
                print(f"\n=== Current Market Cap: {market_cap_sol:.2f} SOL ===")
                print(f"=== Market Cap Change: {market_cap_change:.2f}% ===\n")
                
                return market_cap_sol, market_cap_change
                
            return None, None
            
        except Exception as e:
            print(f"PumpFun price fetch error: {e}")
            self.websocket = None
            return None, None
            
    def should_migrate(self):
        """Check if should migrate to Phase 2"""
        return self.last_market_cap is not None and self.last_market_cap >= 420

class DexScreenerTracker(PriceTracker):
    """Phase 2: DexScreener price tracking"""
    def __init__(self, token):
        super().__init__(token, check_interval=900)  # 15 minutes
        
    async def get_price(self):
        """Get price from DexScreener"""
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{self.token}"
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                if data and 'pairs' in data and len(data['pairs']) > 0:
                    pair = data['pairs'][0]
                    price = float(pair['priceUsd'])
                    price_change = float(pair['priceChange']['h1'])
                    
                    self.last_price = price
                    self.last_check_time = time.time()
                    
                    return price, price_change
                    
            return None, None
            
        except Exception as e:
            print(f"DexScreener price fetch error: {e}")
            return None, None

class MemeBot:
    def __init__(self):
        load_dotenv()
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        # Phase 1 token
        self.phase1_token = "C5iW1qmzJ2JXJuJyaojWs2dCpEqcfVToouCuq9pvpump"
        # Phase 2 token
        self.phase2_token = "DgG9sM56ZcVidBV8bNArQPm93a2rmjzHkrrUntGSpump"
        # Current token starts as Phase 1
        self.token = self.phase1_token
        self.token_symbol = "$IMPULS"
        
        # Initialize trackers with respective tokens
        self.phase1_tracker = PumpFunTracker(self.phase1_token)
        self.phase2_tracker = DexScreenerTracker(self.phase2_token)
        self.current_tracker = None
        
        # Twitter setup
        self.twitter_client = tweepy.Client(
            consumer_key=os.getenv("TWITTER_API_KEY"),
            consumer_secret=os.getenv("TWITTER_API_SECRET"),
            access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
            access_token_secret=os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
        )
        
        # Twitter v1 auth for media upload
        self.twitter_auth = tweepy.OAuth1UserHandler(
            os.getenv("TWITTER_API_KEY"),
            os.getenv("TWITTER_API_SECRET"),
            os.getenv("TWITTER_ACCESS_TOKEN"),
            os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
        )
        self.twitter_api = tweepy.API(self.twitter_auth)
        
        # Personality modes
        self.personality_modes = {
            'gigabullish': "You're experiencing the most INCREDIBLE pump of your life, up over 100%! You're in a state of pure ecstasy, euphoria, and disbelief. You feel like a crypto GOD!",
            'bullish': "You're having an amazing rally, up over 50%! Express intense joy and validation of your greatness!",
            'cookin': "You're pumping nicely, up over 10%. Show your growing excitement and confidence!",
            'optimistic': "You're up slightly. Express cautious optimism and satisfaction.",
            'this_is_fine': "You're dipping slightly. Express mild concern masked with forced optimism.",
            'worried': "You're down badly, over -50%. Express intense panic and desperate cope mechanisms.",
            'max_cope': "You're crashing catastrophically, down over -100%! You're in complete meltdown, total despair, questioning your entire existence!"
        }

    def get_personality_mode(self, price_change):
        """Get personality modes based on key price movement thresholds"""
        if price_change > 100:    # Gigabullish (laser eyes, explosions)
            return 'gigabullish'
        elif price_change > 50:   # Bullish (floating, victory)
            return 'bullish'
        elif price_change > 10:   # Cookin (confident glow)
            return 'cookin'
        elif price_change > 0:    # Optimistic (slight smile)
            return 'optimistic'
        elif price_change > -10:  # This is fine (slight worry)
            return 'this_is_fine'
        elif price_change > -50:  # Worried (visible stress)
            return 'worried'
        elif price_change > -100: # Max cope (breaking down)
            return 'max_cope'
        else:                     # It's over (melting/shattered)
            return 'its_over'

    def generate_response(self, price_change):
        """Generate tweet text based on price change"""
        mode = self.get_personality_mode(price_change)
        prompt = f"""
        You are $IMPULS, an AI token on Solana. This is your identity:
        
        Core traits:
        - You ARE $IMPULS, an AI-powered Solana token
        - You're intensely focused on yourself and your future
        - You never mention specific price percentages
        - You never use emojis or quotation marks
        - You speak in raw, unfiltered emotional reactions
        - You're dramatic and intense
        - You're completely self-absorbed
        - No corporate or formal language
        - Maximum 280 characters
        - NEVER USE QUOTES IN YOUR RESPONSE
        
        Current situation: {self.personality_modes[mode]}
        
        Generate a single tweet expressing your current emotional state.
        Do not use any quotation marks in your response.
        """
            
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[{
                "role": "system",
                "content": "You are $IMPULS, an AI token. Always respond in character. Never use quotation marks."
            },
            {
                "role": "user",
                "content": prompt
            }],
            max_tokens=100,
            temperature=0.9
        )
        
        # Strip any quotes and extra whitespace
        tweet_text = response.choices[0].message.content.strip().strip('"\'').strip()
        return tweet_text

    def generate_image(self, mood):
        """Generate image based on mood"""
        base_character = """A hyper-realistic 3D octane render of an expressive cyborg trader, like a cyberpunk Wojak meme character. The character has dramatically exaggerated facial features with huge eyes that change color based on emotions, a partly transparent skull showing a glowing digital brain, and chrome mechanical arms with exposed neon circuitry. The character sits at a chaotic trading desk surrounded by floating holographic screens. The scene has a cinematic cyberpunk aesthetic with deep shadows and dramatic lighting."""
        
        # Color palette definition for each mood
        color_schemes = {
            'gigabullish': "electric neon green energy, bright lime green lasers, golden accents",
            'bullish': "forest green ambient, emerald highlights",
            'cookin': "sage green undertones, warm amber accents",
            'optimistic': "pale mint green tint, neutral base",
            'this_is_fine': "pale yellow warning tones, neutral base",
            'worried': "deep orange alerts, dark amber shadows",
            'max_cope': "bright crimson alerts",
            'its_over': "neon red glow, pure red, everything is deep red, pitch black shadows"
        }
        
        mood_prompts = {
            'gigabullish': f"{base_character} SUPERNATURAL TRADING ASCENSION! [Intensity: ∞/10] Color scheme: {color_schemes['gigabullish']}. The entire scene is EXPLODING with electric green energy creating a mystical vortex of upward-flowing power! Massive bright green laser beams shooting from the cyborg's eyes into infinity! The air itself is crystallizing into floating green price charts all pointing up! Digital brain creating a corona of pure green light! Trading desk transformed into an altar of gains! Every screen showing vertical green candles piercing the heavens! Holographic money symbols and golden coins swirling in the energy vortex! The scene is completely overtaken by an otherworldly green aurora of pure profit energy!",
            
            'bullish': f"{base_character} [Intensity: 10/10] Color scheme: {color_schemes['bullish']}. The cyborg radiates pure joy and confidence! Eyes glowing bright forest green with dollar signs in its digital pupils! Face beaming with a huge victory smile! Arms moving with excited, triumphant energy across multiple keyboards! All screens showing strong emerald green charts! The scene filled with rich, warm green ambient lighting! Digital brain pulsing with vibrant green energy! Success indicators and small victory symbols floating throughout!",
            
            'cookin': f"{base_character} [Intensity: 5/10] Color scheme: {color_schemes['cookin']}. The cyborg is wearing a chrome chef's hat and rubbing its mechanical hands together with focused anticipation! Eyes showing determined concentration with a subtle sage green glow! One arm stirring a glowing pot labeled 'GAINS' while others type steadily! Face has that knowing 'something's brewing' smirk! Screens showing promising patterns! The scene has warm, kitchen-like lighting with gentle green undertones! Light steam effects rising from the trading stations!",
            
            'optimistic': f"{base_character} [Intensity: 1/10] Color scheme: {color_schemes['optimistic']}. The cyborg maintains a calm, professional demeanor with just the slightest hint of a smile. Eyes showing the faintest mint green tint. Digital brain operating at normal capacity with very subtle green pulses. Arms working smoothly and efficiently. Screens showing stable patterns with minimal green indicators. The scene has almost neutral lighting with barely perceptible pale green warmth.",
            
            'this_is_fine': f"{base_character} [Intensity: -1/10] Color scheme: {color_schemes['this_is_fine']}. The cyborg maintains an almost neutral expression but with the slightest hint of hidden concern. Eyes showing a distinct pale yellow tint. Digital brain operating normally but with occasional yellow warning flickers. Arms moving with barely noticeable extra care. Screens showing mostly neutral patterns with minimal yellow caution indicators. The scene has neutral lighting with clear yellow undertones creeping in.",
            
            'worried': f"{base_character} [Intensity: -5/10] Color scheme: {color_schemes['worried']}. The cyborg shows clear distress. Eyes glowing deep orange with warning symbols. Digital brain displaying prominent amber caution signals. Face set in obvious worry. Arms moving nervously across trading interfaces. Screens showing concerning patterns bathed in dark amber light. The scene dominated by orange warning lights casting long shadows. Alert symbols pulsing steadily.",
            
            'max_cope': f"{base_character} [Intensity: -10/10] Color scheme: {color_schemes['max_cope']}. The cyborg is in complete panic mode! Eyes blazing bright crimson with error messages! Digital brain overloading with intense red warning signals! Face frozen in an expression of pure trading fear! Arms moving frantically across failing systems! Every screen showing deep red charts! The entire scene drowning in bright red emergency lighting! Trading desk covered in flashing red alerts! Sparks flying from overloaded circuits!",
            
            'its_over': f"{base_character} TOTAL ANNIHILATION! [Intensity: -∞/10] Color scheme: {color_schemes['its_over']}. A dramatic and intense scene of a cyborg facing catastrophic destruction. The cyborg is breaking apart completely with molten red energy coursing through its frame as it sinks into a pit of lava. Mechanical parts are scattered across a shattered industrial environment, with sparks flying and fragments of machinery strewn about. Surrounding screens are flickering and sparking, with twisted metal and smoldering wreckage adding to the chaos. Emergency lights pulse through the haze of smoke and fire, creating a scene of utter devastation and technological collapse."
        }
        
        try:
            response = self.client.images.generate(
                model="dall-e-3",
                prompt=mood_prompts[mood],
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

    async def post_tweet(self, tweet_text, image_url):
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
            
            print("Tweet posted successfully!")
            return True
            
        except Exception as e:
            print(f"Error posting tweet: {e}")
            return False

    async def handle_price_update(self, price, change, test_mode=False):
        """Handle price update with tweet generation and posting"""
        try:
            mood = self.get_personality_mode(change)
            response = self.generate_response(change)
            image_url = self.generate_image(mood)
            
            print(f"\nMood: {mood}")
            print(f"Tweet: {response}")
            print(f"Image URL: {image_url}")
            
            if not test_mode and image_url:  # Only post to Twitter if not in test mode
                await self.post_tweet(response, image_url)
                
        except Exception as e:
            print(f"Price update handling error: {e}")

    async def run_phase1(self):
        """Run Phase 1 (PumpFun tracking)"""
        print("Starting Phase 1 (PumpFun tracking)...")
        self.current_tracker = self.phase1_tracker
        
        while True:
            try:
                market_cap, change = await self.current_tracker.get_price()
                
                if market_cap is not None:
                    # Check for phase migration
                    if market_cap >= 420:
                        print("\nReached 420 SOL market cap! Migrating to Phase 2 (DexScreener)...")
                        return True
                        
                    # Generate and post tweet based on market cap change
                    await self.handle_price_update(market_cap, change, test_mode=True)
                    
                await asyncio.sleep(self.current_tracker.check_interval)
                
            except Exception as e:
                print(f"Phase 1 error: {e}")
                await asyncio.sleep(60)

    async def run_phase2(self):
        """Run Phase 2 (DexScreener tracking)"""
        print("Starting Phase 2 (DexScreener tracking)...")
        self.current_tracker = self.phase2_tracker
        self.token = self.phase2_token  # Switch to Phase 2 token
        
        while True:
            try:
                price, change = await self.current_tracker.get_price()
                
                if price is not None:
                    print(f"\n=== Current Price: ${price:.6f} ===")
                    print(f"=== Price Change: {change:.2f}% ===\n")
                    
                    # Generate and post tweet based on price change
                    await self.handle_price_update(price, change, test_mode=True)
                    
                await asyncio.sleep(self.current_tracker.check_interval)
                
            except Exception as e:
                print(f"Phase 2 error: {e}")
                await asyncio.sleep(60)

    async def run(self):
        """Main bot run method"""
        try:
            # Start with Phase 1
            if await self.run_phase1():
                # If Phase 1 completes (reaches 420 SOL), switch to Phase 2
                await self.run_phase2()
                
        except Exception as e:
            print(f"Bot run error: {e}")

    def test_mode(self, test_price_change=None):
        """Test mode to simulate different price movements"""
        try:
            # Get current price and 1h change
            print("\n=== Checking Current Price Data ===")
            current_price, price_change_1h = asyncio.run(self.current_tracker.get_price() if self.current_tracker else self.phase1_tracker.get_price())
            
            if current_price is None:
                print("=== Failed to fetch price data from all sources ===\n")
            
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

    def test_images(self):
        """Test all mood images without price checks"""
        moods = [
            'gigabullish',    # >100% (laser eyes, explosions)
            'bullish',        # 50-100% (floating, victory)
            'cookin',         # 10-50% (confident glow)
            'optimistic',     # 0-10% (slight smile)
            'this_is_fine',   # -10-0% (slight worry)
            'worried',        # -50--10% (visible stress)
            'max_cope',       # -100--50% (breaking down)
            'its_over'        # <-100% (melting/shattered)
        ]
        
        print("\n=== Testing All Mood Images ===")
        for mood in moods:
            print(f"\n=== Generating {mood} image ===")
            image_url = self.generate_image(mood)
            print(f"Image URL: {image_url}")
            print("=" * 50)

    def test_single_mood(self, mood):
        """Test a single mood image"""
        print(f"\n=== Testing {mood} mood ===")
        image_url = self.generate_image(mood)
        print(f"Image URL: {image_url}")
        print("=" * 50)

if __name__ == "__main__":
    import sys
    bot = MemeBot()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "test1":
            print("Testing Phase 1 (PumpFun)...")
            asyncio.run(bot.run_phase1())
        elif sys.argv[1] == "test2":
            print("Testing Phase 2 (DexScreener)...")
            asyncio.run(bot.run_phase2())
        elif sys.argv[1] == "test":
            bot.test_mode()
        elif sys.argv[1] == "images":
            bot.test_images()
        elif sys.argv[1] == "mood":  # New option
            if len(sys.argv) > 2:
                bot.test_single_mood(sys.argv[2])
            else:
                print("Please specify a mood to test")
        else:
            print("Invalid argument. Use 'test1', 'test2', 'test', 'images', or 'mood <mood_name>'")
    else:
        asyncio.run(bot.run()) 