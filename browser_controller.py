"""
Selenium / Undetected-Chromedriver Controller for Telegram Web Clone.
Handles session injection, dashboard verification, and humanized channel visit simulation.
"""

import os
import sys
import time
import random
import re
import json
from typing import Dict, Any, Optional, List

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

# Clean outdated chromedriver paths from PATH so Selenium Manager automatically matches Chrome
if "PATH" in os.environ:
    os.environ["PATH"] = os.pathsep.join(
        [p for p in os.environ["PATH"].split(os.pathsep) if "SeleniumWebDrivers" not in p]
    )

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

try:
    import undetected_chromedriver as uc
    HAS_UC = True
except ImportError:
    HAS_UC = False

import config
from session_decoder import decode_string_session


class TelegramWebController:
    def __init__(self, headless: bool = False, proxy_url: Optional[str] = None):
        self.headless = headless
        self.proxy_url = proxy_url or config.PROXY_URL
        self.current_channel = ""
        self.current_action = "Initializing Browser"
        self.cycle_count = 0
        self.total_channels_visited = 0
        self.is_paused = False
        self.skip_requested = False
        self.driver = self._create_driver()

    def get_screenshot_base64(self, max_width: int = 1280, quality: int = 65) -> Optional[str]:
        """
        Captures and compresses a JPEG screenshot of the virtual GUI Chrome screen.
        Minimizes WebSocket bandwidth and keeps latency minimal.
        """
        if not self.driver:
            return None
        try:
            png_data = self.driver.get_screenshot_as_png()
            try:
                from PIL import Image
                import io
                import base64
                img = Image.open(io.BytesIO(png_data))
                if img.mode != "RGB":
                    img = img.convert("RGB")
                if img.width > max_width:
                    ratio = max_width / float(img.width)
                    new_height = int(float(img.height) * float(ratio))
                    img = img.resize((max_width, new_height), Image.Resampling.BILINEAR)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=quality, optimize=True)
                return base64.b64encode(buf.getvalue()).decode("ascii")
            except Exception:
                return self.driver.get_screenshot_as_base64()
        except Exception:
            return None

    def _create_driver(self) -> webdriver.Chrome:
        """
        Initializes Chrome with anti-detection flags and custom configuration.
        """
        driver = None
        if HAS_UC and not self.headless:
            try:
                version_main = None
                try:
                    import subprocess
                    out = subprocess.check_output(["google-chrome", "--version"], text=True)
                    match = re.search(r"(\d+)\.", out)
                    if match:
                        version_main = int(match.group(1))
                except Exception:
                    pass

                options = uc.ChromeOptions()
                options.set_capability("unhandledPromptBehavior", "accept")
                options.add_argument(f"--window-size={config.BROWSER_WINDOW_SIZE[0]},{config.BROWSER_WINDOW_SIZE[1]}")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-gpu")
                if config.USER_AGENT:
                    options.add_argument(f"user-agent={config.USER_AGENT}")
                if self.proxy_url:
                    options.add_argument(f"--proxy-server={self.proxy_url}")
                
                kwargs = {"options": options}
                if version_main:
                    kwargs["version_main"] = version_main
                driver = uc.Chrome(**kwargs)
            except Exception as e:
                print(f"[!] Warning: undetected_chromedriver launch failed ({e}). Falling back to standard Chrome driver...")
                driver = None

        if driver is None:
            # Fallback to standard Selenium Chrome driver (with anti-bot CDP patches)
            options = Options()
            options.set_capability("unhandledPromptBehavior", "accept")
            if self.headless:
                options.add_argument("--headless=new")
            options.add_argument(f"--window-size={config.BROWSER_WINDOW_SIZE[0]},{config.BROWSER_WINDOW_SIZE[1]}")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            if config.USER_AGENT:
                options.add_argument(f"user-agent={config.USER_AGENT}")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            if self.proxy_url:
                options.add_argument(f"--proxy-server={self.proxy_url}")
            
            driver = webdriver.Chrome(options=options)
            
            # Patch navigator.webdriver in standard driver
            driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
            )

        driver.set_page_load_timeout(30)
        driver.set_script_timeout(10)
        return driver

    def inject_session(self, session_string: str, user_id: str = "12345678", target_url: str = None) -> bool:
        """
        Navigates to the local clone origin and executes dual-tier session injection.
        """
        target_url = (target_url or "").strip() or (config.LOCAL_WEB_URL or "").strip() or "https://0xvarcel.github.io"
        print(f"[*] Navigating to local Telegram Web instance at {target_url}...")
        self.driver.get(target_url)
        time.sleep(2)  # Allow origin initialization

        # Decode StringSession
        decoded = decode_string_session(session_string)
        payload = {
            "dc_id": decoded["dc_id"],
            "auth_key_array": decoded["auth_key_list"],
            "auth_key_hex": decoded["auth_key_hex"],
            "user_id": str(user_id),
            "server_time_offset": 0
        }

        # Read injector script
        injector_path = os.path.join(os.path.dirname(__file__), "injector.js")
        with open(injector_path, "r", encoding="utf-8") as f:
            injector_script = f.read()

        print("[*] Executing dual-tier storage injection (IndexedDB + localStorage)...")
        try:
            result = self.driver.execute_async_script(injector_script, payload)
        except Exception as e:
            print(f"[!] Warning during script execution: {e}")
            # If async script timed out, verify if localStorage was written
            ls_check = self.driver.execute_script("return localStorage.getItem('account1');")
            if ls_check:
                result = {"success": True, "message": "localStorage written successfully"}
            else:
                result = {"success": False, "error": str(e)}

        print(f"[+] Injection Result: {result}")

        if not result or not result.get("success"):
            print(f"[!] Injection failed: {result}")
            return False

        print("[*] Refreshing browser page to initialize authenticated session...")
        self.driver.refresh()
        time.sleep(3)
        return True

    def wait_for_dashboard(self, timeout: int = 15) -> bool:
        """
        Verifies that the dashboard has rendered and the login screen was bypassed.
        """
        print("[*] Waiting for Telegram dashboard authentication state...")
        selectors = [
            "#middle-column",
            ".chat-list",
            ".Transition_slide-active",
            "#Main",
            ".sidebar-header"
        ]
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            # Safely check and dismiss any unexpected alert if Vite/Teact displayed one
            try:
                alert = self.driver.switch_to.alert
                alert_text = alert.text
                print(f"[!] Dismissing unexpected browser alert: {alert_text[:60]}...")
                alert.accept()
            except Exception:
                pass

            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and any(e.is_displayed() for e in elements):
                        print(f"[OK] Dashboard detected via selector: {selector}")
                        return True
                except Exception:
                    pass

            time.sleep(1)

        print("[!] Notice: Dashboard selector not confirmed yet. Session is active in browser.")
        return False

    def open_channel(self, channel_target: str, base_url: Optional[str] = None):
        """
        Opens a target channel or chat by formatting the navigation URL or hash.
        Supports:
        - "durov"
        - "@durov"
        - "https://t.me/durov"
        - "t.me/durov"
        """
        cleaned = channel_target.strip()
        # Extract username if given a URL
        match = re.search(r"(?:t\.me/|telegram\.me/|@)?([a-zA-Z0-9_]{4,})", cleaned)
        if match:
            username = match.group(1)
        else:
            username = cleaned.lstrip("@")

        if not base_url:
            current_url = self.driver.current_url
            if current_url and current_url.startswith("http"):
                from urllib.parse import urlparse
                parsed = urlparse(current_url)
                base_url = f"{parsed.scheme}://{parsed.netloc}"
            else:
                base_url = config.LOCAL_WEB_URL

        print(f"[*] Navigating to channel @{username}...")
        # Telegram Web A direct hashtag resolution format
        channel_web_url = f"{base_url.rstrip('/')}/#@{username}"
        self.driver.get(channel_web_url)
        time.sleep(1)

    def simulate_channel_reading(self, channel_target: str = "", duration_seconds: int = 30, base_url: Optional[str] = None):
        """
        Humanized Channel Visit & DOM Selector Scroll Simulation:
        - Automatically finds the active message container selector
        - Simulates natural human reading physics (variable velocity, smooth scroll)
        - 15% probability of backtracking / scrolling up to mimic re-reading
        - Random mouse cursor micro-drifts over message elements
        - Realistic reading pauses between scroll bursts
        """
        if channel_target:
            self.open_channel(channel_target, base_url=base_url)

        print(f"[*] Starting humanized reading simulation for {duration_seconds}s...")
        actions = ActionChains(self.driver)
        start_time = time.time()
        scroll_count = 0

        # JavaScript snippet to identify and scroll the active message container
        scroll_js = """
        function getScrollTarget() {
            const selectors = [
                '.MessageList',
                '.messages-layout',
                '.bubbles',
                '#middle-column .scrollable',
                '.history-full-height',
                '.chat-history',
                'main .scrollable',
                '.messages-container'
            ];
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (el && el.scrollHeight > el.clientHeight) {
                    return { el: el, isWindow: false, selector: sel };
                }
            }
            return { el: document.scrollingElement || document.documentElement, isWindow: true, selector: 'window' };
        }

        const targetInfo = getScrollTarget();
        const delta = arguments[0];
        
        if (targetInfo.isWindow) {
            window.scrollBy({ top: delta, behavior: 'smooth' });
        } else {
            targetInfo.el.scrollBy({ top: delta, behavior: 'smooth' });
        }
        return targetInfo.selector;
        """

        while time.time() - start_time < duration_seconds:
            scroll_count += 1
            
            # 1. Decide scroll direction and magnitude
            # 85% forward scroll, 15% slight backward scroll (re-reading prior message)
            if scroll_count > 2 and random.random() < 0.15:
                # Scroll UP slightly
                delta = -random.randint(60, 150)
                scroll_type = "Rewind (Re-reading)"
            else:
                # Scroll DOWN naturally
                delta = random.randint(180, 420)
                scroll_type = "Reading Forward"

            active_selector = self.driver.execute_script(scroll_js, delta)

            # 2. Subtle cursor movement / drift over message bubbles
            if config.RANDOM_MOUSE_DRIFT:
                try:
                    # Hover over visible message elements if present
                    message_elements = self.driver.find_elements(By.CSS_SELECTOR, ".message-content, .bubble, .Message, .text-content")
                    if message_elements and random.random() < 0.4:
                        target_elem = random.choice(message_elements[-5:])
                        if target_elem.is_displayed():
                            actions.move_to_element(target_elem).perform()
                    else:
                        offset_x = random.randint(-25, 25)
                        offset_y = random.randint(-15, 15)
                        actions.move_by_offset(offset_x, offset_y).perform()
                except Exception:
                    pass

            # 3. Dynamic human reading pauses
            # Varies between quick glance (1.5s) and thorough reading (4.5s - 6.0s)
            pause_time = random.uniform(config.SCROLL_MIN_PAUSE, config.SCROLL_MAX_PAUSE)
            remaining = duration_seconds - (time.time() - start_time)
            actual_pause = min(pause_time, max(0.5, remaining))
            
            print(f"  [>] {scroll_type} ({delta:+d}px on {active_selector}) -> reading pause: {actual_pause:.1f}s")
            time.sleep(actual_pause)

        print("[OK] Channel visit simulation complete.")

    def _move_mouse_curved(self, target_elem=None, offset_x: int = 0, offset_y: int = 0, steps: int = 8):
        """
        [FEATURE 1] Bézier Curve Mouse Trajectory:
        Moves mouse cursor along a smooth curved trajectory with variable acceleration
        and micro-jitter, mimicking real human hand-motor physics.
        """
        try:
            actions = ActionChains(self.driver)
            if target_elem:
                actions.move_to_element(target_elem).perform()
            elif offset_x != 0 or offset_y != 0:
                dx = offset_x / steps
                dy = offset_y / steps
                for i in range(steps):
                    jx = random.uniform(-1.5, 1.5)
                    jy = random.uniform(-1.5, 1.5)
                    actions.move_by_offset(dx + jx, dy + jy).perform()
                    time.sleep(random.uniform(0.015, 0.035))
        except Exception:
            pass

    def _park_cursor_margin(self):
        """
        [FEATURE 1] Margin Cursor Parking:
        Parks cursor in the neutral margin whitespace while reading text,
        mimicking real desktop users who move the cursor away from content.
        """
        try:
            actions = ActionChains(self.driver)
            actions.move_by_offset(random.randint(20, 45), random.randint(-15, 15)).perform()
        except Exception:
            pass

    def _maybe_simulate_text_highlight(self):
        """
        [FEATURE 1] Natural Text Drag Highlighting:
        With ~15% probability, drag-selects a few words or a sentence as if using
        the cursor as a visual reading guide, pauses, then clicks away.
        """
        if random.random() >= 0.16:
            return
        try:
            content_nodes = self.driver.find_elements(By.CSS_SELECTOR, ".message-content .text-content, .message-content p, .Message .text-content")
            visible = [c for c in content_nodes if c.is_displayed() and len(c.text.strip()) > 15]
            if not visible:
                return
            node = random.choice(visible[-4:])
            print("  [~] Human habit: Drag-selecting text along reading line...")
            actions = ActionChains(self.driver)
            actions.move_to_element(node).pause(0.2).click_and_hold().move_by_offset(random.randint(40, 95), 0).pause(random.uniform(0.5, 1.0)).release().perform()
            time.sleep(random.uniform(0.4, 0.8))
            # Unselect / clear text highlight
            self.driver.execute_script("if (window.getSelection) { window.getSelection().removeAllRanges(); }")
        except Exception:
            pass

    def _calculate_dynamic_reading_pause(self, default_min: float = 2.0, default_max: float = 4.5) -> float:
        """
        [FEATURE 2] Dynamic Word-Count Based Reading Dwell:
        Calculates reading pause dynamically based on the word count of visible messages.
        Humans read at ~200-240 words per minute (~3.8 words per second).
        Adds extra glance time (+1.5-3.0s) for embedded photos or media.
        """
        try:
            msg_texts = self.driver.find_elements(By.CSS_SELECTOR, ".message-content, .text-content")
            visible_texts = [m.text for m in msg_texts[-4:] if m.is_displayed() and m.text]
            total_words = sum(len(t.split()) for t in visible_texts)

            # Human reading speed: ~3.8 words per second
            reading_time = total_words / 3.8

            # Media thumbnail check
            media_count = len(self.driver.find_elements(By.CSS_SELECTOR, ".Photo, .media-inner, [class*='album-item']"))
            media_glance = min(5.0, media_count * 1.5)

            total_pause = max(default_min, min(10.0, reading_time + media_glance + random.uniform(0.8, 1.8)))
            return total_pause
        except Exception:
            return random.uniform(default_min, default_max)

    def _maybe_inspect_media(self):
        """
        [FEATURE 4] Photo & Media Full-Screen Preview:
        With ~25% probability, clicks a visible photo or video in the chat stream,
        views it full-screen in MediaViewer for 2.5 - 4.5s, then presses Escape to close.
        """
        if random.random() >= 0.28:
            return

        try:
            media_elems = self.driver.find_elements(By.CSS_SELECTOR, ".Photo img, .media-inner img, [class*='Photo_root'], [class*='album-item'] img, .media-inner")
            visible = [m for m in media_elems if m.is_displayed()]
            if not visible:
                return

            target_media = random.choice(visible[-3:])
            print("[*] Human curiosity: Opening photo preview in MediaViewer...")
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", target_media)
            time.sleep(random.uniform(0.6, 1.2))

            ActionChains(self.driver).move_to_element(target_media).pause(0.3).click().perform()

            # Linger inside media viewer
            view_time = random.uniform(2.5, 4.5)
            print(f"  [>] Inspecting photo for {view_time:.1f}s...")
            time.sleep(view_time)

            # Close media viewer with Escape key
            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            print("[OK] Closed photo preview, returning to chat stream.")
            time.sleep(random.uniform(0.8, 1.5))
        except Exception:
            try:
                ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            except Exception:
                pass

    def _maybe_peek_pinned_message(self):
        """
        [FEATURE 5] Pinned Message Bar Inspection:
        With ~18% probability, glances at the pinned message announcement bar in the header,
        reads it for 2.0 - 3.5s, and then returns to the latest messages.
        """
        if random.random() >= 0.20:
            return

        try:
            pinned_bar = self.driver.find_elements(By.CSS_SELECTOR, ".HeaderPinnedMessageWrapper, [class*='HeaderPinnedMessage'], .pinned-message")
            visible = [p for p in pinned_bar if p.is_displayed()]
            if not visible:
                return

            print("[*] Human curiosity: Checking pinned announcement bar...")
            ActionChains(self.driver).move_to_element(visible[0]).pause(0.3).click().perform()

            # Read pinned message
            pinned_read = random.uniform(2.0, 3.5)
            print(f"  [>] Reading pinned announcement for {pinned_read:.1f}s...")
            time.sleep(pinned_read)

            # Return to bottom
            scroll_down_btn = self.driver.find_elements(By.CSS_SELECTOR, ".Button.scroll-down, .jump-to-bottom, [aria-label*='bottom']")
            if scroll_down_btn and scroll_down_btn[0].is_displayed():
                ActionChains(self.driver).move_to_element(scroll_down_btn[0]).pause(0.2).click().perform()
            else:
                self.driver.execute_script("window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});")
            print("[OK] Returned to latest messages.")
            time.sleep(1.0)
        except Exception:
            pass

    def _maybe_vote_poll(self):
        """
        [FEATURE 6] Community Poll Interaction:
        With ~15% probability, checks if an unvoted poll is visible in recent messages,
        selects a random option and casts a vote.
        """
        if random.random() >= 0.18:
            return

        try:
            poll_options = self.driver.find_elements(By.CSS_SELECTOR, "[class*='PollOption_root'], [class*='Poll_options'] [class*='option'], .poll-answer")
            visible_options = [o for o in poll_options if o.is_displayed()]
            if not visible_options:
                return

            chosen_opt = random.choice(visible_options[:4])
            print("[*] Community engagement: Voting in visible poll...")
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", chosen_opt)
            time.sleep(random.uniform(0.6, 1.2))

            ActionChains(self.driver).move_to_element(chosen_opt).pause(random.uniform(0.3, 0.6)).click().perform()
            print("[+] Cast vote in poll! Observing results...")
            time.sleep(random.uniform(1.5, 2.5))
        except Exception:
            pass

    def _maybe_switch_tab_briefly(self):
        """
        [FEATURE 7] Multitasking Tab Switching & Blur Simulation:
        With ~20% probability, opens a secondary blank tab to simulate multitasking
        (checking another window/tab for 4.0 - 8.0s), then switches back to Telegram.
        This triggers authentic window.blur and window.focus browser events.
        """
        if random.random() >= 0.22:
            return

        try:
            print("[*] Simulating multitasking: Switching to background tab...")
            original_handle = self.driver.current_window_handle
            self.driver.execute_script("window.open('about:blank', '_blank');")
            time.sleep(0.5)

            all_handles = self.driver.window_handles
            new_handle = [h for h in all_handles if h != original_handle]
            if new_handle:
                self.driver.switch_to.window(new_handle[-1])
                away_time = random.uniform(4.0, 8.0)
                print(f"  [>] In other tab for {away_time:.1f}s (Telegram tab blurred)...")
                time.sleep(away_time)
                self.driver.close()
                self.driver.switch_to.window(original_handle)
                print("[OK] Switched back to Telegram (tab focused).")
                time.sleep(1.0)
        except Exception:
            try:
                if original_handle in self.driver.window_handles:
                    self.driver.switch_to.window(original_handle)
            except Exception:
                pass

    def search_and_open_channel(self, username: str, target_name: str = "", timeout: int = 10) -> bool:
        """
        Searches for a channel via the Telegram Web search input bar:
        1. Formats username with '@'
        2. Types query with human-like randomized keystroke delays and natural typos (Feature 3)
        3. Waits for search results to populate in the left column
        4. Compares search result titles against target_name for verification
        5. Clicks the matched channel with natural Bézier mouse movement
        """
        query = username.strip()
        if not query.startswith("@") and not query.startswith("http"):
            query = f"@{query}"

        print(f"[*] Searching for channel {query} via web app search bar...")

        search_selectors = [
            "#telegram-search-input",
            ".SearchInput input",
            "#LeftMainHeader input",
            "input.form-control",
            "input[placeholder*='Search']",
            ".input-search-input"
        ]

        search_input = None
        for sel in search_selectors:
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for el in elems:
                    if el.is_displayed():
                        search_input = el
                        break
                if search_input:
                    break
            except Exception:
                pass

        actions = ActionChains(self.driver)

        if search_input:
            try:
                search_input.click()
                time.sleep(random.uniform(0.3, 0.6))
                # Clear existing text
                search_input.send_keys(Keys.CONTROL + "a")
                search_input.send_keys(Keys.BACKSPACE)
                time.sleep(random.uniform(0.2, 0.5))

                # [FEATURE 3] Human-like typing with QWERTY typo injection and backspace correction
                qwerty_neighbors = {
                    'a': 'qwsz', 'b': 'vghn', 'c': 'xdfv', 'd': 'ersfxc', 'e': 'wsdr',
                    'f': 'rtgvcd', 'g': 'tyhbvf', 'h': 'yujnbg', 'i': 'ujko', 'j': 'uikmnh',
                    'k': 'ijlm', 'l': 'kop', 'm': 'njk', 'n': 'bhjm', 'o': 'iklp',
                    'p': 'ol', 'q': 'wa', 'r': 'edft', 's': 'wedxza', 't': 'rfgy',
                    'u': 'yhji', 'v': 'cfgb', 'w': 'qase', 'x': 'zsdc', 'y': 'tghu', 'z': 'asx'
                }

                typo_happened = False
                typo_idx = random.randint(3, len(query) - 2) if len(query) >= 6 and random.random() < 0.22 else -1

                for idx, ch in enumerate(query):
                    if idx == typo_idx and not typo_happened:
                        # Type an adjacent typo
                        wrong_ch = random.choice(qwerty_neighbors.get(ch.lower(), 'aeiou'))
                        search_input.send_keys(wrong_ch)
                        # Cognitive realization lag
                        time.sleep(random.uniform(0.22, 0.42))
                        # Hit backspace to correct
                        search_input.send_keys(Keys.BACKSPACE)
                        time.sleep(random.uniform(0.12, 0.25))
                        typo_happened = True

                    search_input.send_keys(ch)
                    time.sleep(random.uniform(0.05, 0.13))

                # Wait for search results to populate
                search_wait = random.uniform(2.5, 4.0)
                print(f"[*] Search query entered. Waiting {search_wait:.1f}s for results to load...")
                time.sleep(search_wait)

                # Search result item selectors in Telegram Web A
                result_selectors = [
                    ".LeftSearch .search-result",
                    ".LeftSearch .chat-item-clickable",
                    ".LeftSearch .ListItem-button",
                    "#LeftColumn .search-result",
                    ".LeftSearch .ChatInfo",
                    ".chat-item-clickable"
                ]

                result_items = []
                for r_sel in result_selectors:
                    try:
                        elems = self.driver.find_elements(By.CSS_SELECTOR, r_sel)
                        visible_elems = [e for e in elems if e.is_displayed()]
                        if visible_elems:
                            result_items = visible_elems
                            break
                    except Exception:
                        pass

                def clean_text(s: str) -> str:
                    return re.sub(r'[^\w\s]', '', s.lower()).strip()

                target_norm = clean_text(target_name)
                matched_elem = None

                if result_items:
                    print(f"[+] Found {len(result_items)} search result items. Verifying channel title...")
                    for item in result_items:
                        try:
                            # Look for title inside result item (.fullName or heading)
                            title_elems = item.find_elements(By.CSS_SELECTOR, ".fullName, h3, .title, .info")
                            item_text = title_elems[0].text if title_elems else item.text
                            item_norm = clean_text(item_text)

                            if target_norm and (target_norm in item_norm or item_norm in target_norm):
                                print(f"[+] Match confirmed: '{item_text.strip()}' matches target '{target_name}'")
                                matched_elem = item
                                break
                            elif clean_text(query) in item_norm:
                                matched_elem = item
                                break
                        except Exception:
                            continue

                    # If exact title match wasn't found, pick the top search result
                    if not matched_elem and result_items:
                        matched_elem = result_items[0]
                        print(f"[*] Selecting top search result for {query}: '{matched_elem.text.strip().replace(chr(10), ' | ')}'")

                if matched_elem:
                    self._move_mouse_curved(target_elem=matched_elem)
                    matched_elem.click()
                    print(f"[+] Clicked channel from search results!")
                    time.sleep(1.5)
                    return True

            except Exception as e:
                print(f"[!] Notice during search interaction: {e}")

        # Fallback to direct navigation if search input or click didn't resolve
        print(f"[*] Fallback: Navigating directly to {query}...")
        self.open_channel(query)
        time.sleep(1.5)
        return True

    def react_to_latest_message(self) -> bool:
        """
        Randomly reacts to the latest message in the active channel:
        - Randomized decision: ~55% probability to react, ~45% to skip (mimics human variance)
        - Finds the last visible message in the chat
        - Context clicks (Right-clicks) to open the Telegram reaction menu
        - Selects and clicks a random available reaction emoji
        - If reactions are restricted, safely closes menu without errors
        """
        # Randomized probability (some channels receive reaction, some don't)
        if random.random() >= 0.55:
            print("[*] Random decision: Skipping reaction on this channel (humanized variance).")
            return False

        print("[*] Random decision: Reacting to latest post...")
        try:
            msg_selectors = [
                ".MessageList .Message",
                ".messages-layout .Message",
                "#middle-column .Message",
                ".message-date-group .Message",
                ".bubbles .bubble",
                ".Message"
            ]

            messages = []
            for sel in msg_selectors:
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    visible = [e for e in elems if e.is_displayed()]
                    if visible:
                        messages = visible
                        break
                except Exception:
                    pass

            if not messages:
                print("[!] No visible message elements found to react to.")
                return False

            last_msg = messages[-1]

            # Scroll the latest message into view smoothly
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", last_msg)
            time.sleep(random.uniform(0.8, 1.4))

            # Right-click (context click) on the latest post
            actions = ActionChains(self.driver)
            actions.move_to_element(last_msg).pause(random.uniform(0.3, 0.6)).context_click(last_msg).perform()
            time.sleep(random.uniform(1.0, 1.8))

            # Look for Telegram Web A reaction bar selector
            reaction_selectors = [
                ".ReactionSelectorReaction",
                ".ReactionSelector [class*='root']",
                ".ReactionSelector img",
                ".ReactionSelector > div",
                ".ContextMenu .ReactionSelector div"
            ]

            reaction_elements = []
            for r_sel in reaction_selectors:
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, r_sel)
                    visible_r = [e for e in elems if e.is_displayed()]
                    if visible_r:
                        reaction_elements = visible_r
                        break
                except Exception:
                    pass

            if reaction_elements:
                chosen = random.choice(reaction_elements[:6])
                actions.move_to_element(chosen).pause(random.uniform(0.3, 0.6)).click().perform()
                print("[+] Successfully reacted to latest post with emoji!")
                time.sleep(1.0)
                return True

            # Fallback: check if the message already has reaction chips at the bottom
            existing_reactions = last_msg.find_elements(By.CSS_SELECTOR, ".Reactions button, [class*='ReactionButton']")
            if existing_reactions:
                chosen_chip = random.choice(existing_reactions)
                chosen_chip.click()
                print("[+] Clicked existing reaction button on latest post!")
                time.sleep(0.8)
                return True

            # If no reaction UI appeared (e.g. reactions disabled by channel admin), dismiss context menu
            actions.send_keys(Keys.ESCAPE).perform()
            print("[*] Reactions not available on this post. Context menu dismissed.")
            return False

        except Exception as e:
            print(f"[!] Warning during reaction: {e}")
            try:
                ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            except Exception:
                pass
            return False

    def simulate_human_channel_visit(self, channel_data: dict, min_dwell: int = 30, max_dwell: int = 60):
        """
        Executes a complete, highly realistic humanized channel visit lifecycle:
        1. Searches for channel username on web app (with human typos & backspace) and verifies name
        2. Waits random 2-5 seconds upon opening, parking cursor in neutral whitespace
        3. Glances at pinned announcement bar if present
        4. Scrolls naturally down to latest posts with dynamic word-count reading dwell times
        5. Performs organic text drag-highlighting while reading
        6. Rewinds slightly up (re-reading simulation) and scrolls back down
        7. Simulates 2-3 mouse wheel bottom-scroll nudges
        8. Inspects photos/videos in full-screen MediaViewer
        9. Participates in visible community polls
        10. Randomly reacts to the latest post with right-click
        11. Simulates brief background multitasking (window blur/focus tab switch)
        12. Lingers and observes for 30s to 60s total dwell time
        """
        name = channel_data.get("name", "Unknown Channel")
        username = channel_data.get("username", "")
        self.current_channel = f"{name} ({username})"
        self.current_action = f"Reading '{name}'"
        dwell_time = random.uniform(min_dwell, max_dwell)
        start_time = time.time()

        print("\n" + "=" * 65)
        print(f"[*] Visiting Channel: '{name}' ({username})")
        print(f"[*] Planned Dwell Time: {dwell_time:.1f}s (Randomized {min_dwell}s - {max_dwell}s)")
        print("=" * 65)

        # 1. Search and open channel (includes Feature 3: Typos & Backspace)
        self.search_and_open_channel(username, target_name=name)

        # 2. Random initial pause (2 to 5 seconds) with margin cursor parking (Feature 1)
        init_pause = random.uniform(2.0, 5.0)
        print(f"[*] Channel opened. Initial reading pause: {init_pause:.1f}s...")
        self._park_cursor_margin()
        time.sleep(init_pause)

        # Check pause / skip
        while self.is_paused:
            time.sleep(0.5)
        if self.skip_requested:
            self.skip_requested = False
            return

        # 3. Check for pinned message peek (Feature 5)
        self._maybe_peek_pinned_message()

        # JavaScript snippet for smooth natural scrolling on active message container
        scroll_js = """
        function scrollTarget(delta) {
            const selectors = [
                '.MessageList',
                '.messages-layout',
                '.bubbles',
                '#middle-column .scrollable',
                '.chat-history',
                'main .scrollable'
            ];
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (el && el.scrollHeight > el.clientHeight) {
                    el.scrollBy({ top: delta, behavior: 'smooth' });
                    return sel;
                }
            }
            window.scrollBy({ top: delta, behavior: 'smooth' });
            return 'window';
        }
        return scrollTarget(arguments[0]);
        """

        # 4. Natural human-like scrolling down towards latest posts
        print("[*] Scrolling down through channel messages...")
        scroll_steps = random.randint(4, 7)
        for i in range(scroll_steps):
            delta = random.randint(220, 450)
            target = self.driver.execute_script(scroll_js, delta)
            
            # Feature 2: Dynamic word-count reading dwell
            reading_pause = self._calculate_dynamic_reading_pause(default_min=1.8, default_max=4.0)
            print(f"  [>] Reading forward (+{delta}px on {target}) -> dynamic pause: {reading_pause:.1f}s")
            
            # Feature 1: Park cursor in margin
            self._park_cursor_margin()
            time.sleep(reading_pause)

            # Feature 1: Occasional text drag highlight
            self._maybe_simulate_text_highlight()

        # 5. Rewind slightly (re-reading prior message) & scroll back down
        rewind_delta = -random.randint(180, 320)
        self.driver.execute_script(scroll_js, rewind_delta)
        rewind_pause = self._calculate_dynamic_reading_pause(default_min=1.8, default_max=3.2)
        print(f"  [<] Re-reading rewind ({rewind_delta}px) -> pause: {rewind_pause:.1f}s")
        time.sleep(rewind_pause)

        forward_delta = random.randint(250, 420)
        self.driver.execute_script(scroll_js, forward_delta)
        print(f"  [>] Returning to latest post (+{forward_delta}px)...")
        time.sleep(random.uniform(1.5, 2.5))

        # 6. Simulate 2-3 mouse wheel bottom-scroll nudges (human gesture)
        print("[*] Simulating mouse wheel bottom-scroll nudges...")
        for _ in range(random.randint(2, 3)):
            self.driver.execute_script(scroll_js, 90)
            time.sleep(random.uniform(0.7, 1.3))

        # 7. Check for photo preview curiosity (Feature 4)
        self._maybe_inspect_media()

        # 8. Check for poll engagement (Feature 6)
        self._maybe_vote_poll()

        # 9. Random reaction on latest post
        self.react_to_latest_message()

        # 10. Check for multitasking tab switch (Feature 7)
        self._maybe_switch_tab_briefly()

        # 11. Complete remaining dwell time
        while time.time() - start_time < dwell_time:
            remaining = dwell_time - (time.time() - start_time)
            step_pause = min(random.uniform(2.0, 4.0), max(0.5, remaining))
            if config.RANDOM_MOUSE_DRIFT:
                self._move_mouse_curved(offset_x=random.randint(-20, 20), offset_y=random.randint(-15, 15))
            time.sleep(step_pause)

        total_spent = time.time() - start_time
        print(f"[OK] Completed visit for '{name}'. Total time: {total_spent:.1f}s")

    @staticmethod
    def load_channels(source: str = config.CHANNELS_SOURCE_URL) -> List[Dict[str, Any]]:
        """
        Loads the channel list directly into memory from a remote URL (https://chvisit.pages.dev/chvisit.json)
        or optional local file path without storing any local JSON files in the project folder.
        """
        import urllib.request
        channels = []

        if source.startswith("http://") or source.startswith("https://"):
            print(f"[*] Fetching live channel list from remote URL: {source}...")
            try:
                req = urllib.request.Request(
                    source,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                )
                with urllib.request.urlopen(req, timeout=12) as resp:
                    raw_data = resp.read().decode("utf-8")
                    channels = json.loads(raw_data)
                    print(f"[+] Successfully fetched {len(channels)} channels directly from remote URL into memory!")
                    return channels
            except Exception as e:
                print(f"[!] Warning: Remote channel fetch from '{source}' failed: {e}")

        # If a local file path was explicitly provided
        if not source.startswith("http") and os.path.exists(source):
            try:
                with open(source, "r", encoding="utf-8") as f:
                    channels = json.load(f)
                print(f"[+] Loaded {len(channels)} channels from local file '{source}'.")
                return channels
            except Exception as e:
                print(f"[!] Error reading local file '{source}': {e}")
        elif not source.startswith("http"):
            print(f"[!] Error: Local channel file '{source}' not found.")

        return channels

    def run_channel_visit_cycle(
        self,
        source: str = config.CHANNELS_SOURCE_URL,
        cycle_break_min: int = 120,
        cycle_break_max: int = 300,
        max_cycles: Optional[int] = None
    ):
        """
        Continuous Multi-Channel Humanized Automation Cycle:
        1. Dynamically fetches channels list from remote URL or local file
        2. Iterates through each channel sequentially:
           - Searches username on web app
           - Verifies channel title
           - Spends 30-60 seconds in channel with natural scrolls and random reactions
        3. After visiting all channels in the list, takes a random break of 2-5 minutes (120-300s)
        4. Re-fetches the channel list at the start of every cycle to reflect any updates
        5. Restarts from Channel #1 automatically in a loop (or exits if max_cycles reached)
        """
        print("\n" + "#" * 65)
        print("STARTING CONTINUOUS CHANNEL VISIT CYCLE AUTOMATION")
        print(f"[*] Channels Source: {source}")
        print(f"[*] Dwell Time per Channel: 30s - 60s (Randomized)")
        print(f"[*] Break Between Cycles: {cycle_break_min/60:.1f} - {cycle_break_max/60:.1f} minutes")
        if max_cycles:
            print(f"[*] Maximum Cycles to Run: {max_cycles}")
        print("#" * 65)

        cycle_count = 0
        while True:
            cycle_count += 1
            print(f"\n{'='*25} STARTING CYCLE #{cycle_count} {'='*25}")

            # Re-fetch at the start of each cycle so any edits on https://chvisit.pages.dev/chvisit.json
            # are dynamically detected without restarting the script!
            channels = self.load_channels(source)
            if not channels:
                print("[!] No channels available to visit. Retrying in 30 seconds...")
                time.sleep(30)
                continue

            for idx, ch in enumerate(channels, 1):
                while self.is_paused:
                    time.sleep(0.5)
                if self.skip_requested:
                    self.skip_requested = False
                    continue

                self.cycle_count = cycle_count
                self.current_action = f"Channel {idx}/{len(channels)} (Cycle #{cycle_count})"
                print(f"\n--- [Cycle #{cycle_count} | Channel {idx}/{len(channels)}] ---")
                self.simulate_human_channel_visit(ch, min_dwell=30, max_dwell=60)
                self.total_channels_visited += 1

                # Buffer pause between channel transitions (3 to 7 seconds)
                if idx < len(channels):
                    pause_between = random.uniform(3.0, 7.0)
                    print(f"[*] Moving to next channel in {pause_between:.1f}s...")
                    time.sleep(pause_between)

            # Cycle completed!
            print("\n" + "*" * 65)
            print(f"[OK] Completed all {len(channels)} channels in Cycle #{cycle_count}!")

            # Check if maximum cycles reached
            if max_cycles is not None and cycle_count >= max_cycles:
                print(f"[OK] Reached target max cycles ({max_cycles}). Exiting automation loop successfully.")
                print("*" * 65)
                break

            # Take a 2 to 5 minute break before restarting
            cycle_break = random.uniform(cycle_break_min, cycle_break_max)
            self.current_action = f"Cycle Break ({int(cycle_break)}s)"
            self.current_channel = "Resting between cycles"
            print(f"[*] Taking humanized cycle break: {cycle_break/60:.2f} minutes ({cycle_break:.0f}s)...")
            print("    The browser remains open and session stays active.")
            print("*" * 65)

            break_start = time.time()
            while time.time() - break_start < cycle_break:
                while self.is_paused:
                    time.sleep(0.5)
                if self.skip_requested:
                    self.skip_requested = False
                    print("[*] Skip break requested from Admin Panel. Resuming cycle now...")
                    break
                time.sleep(min(2.0, cycle_break - (time.time() - break_start)))

            print(f"\n[*] Cycle break complete! Re-fetching channels and restarting from Channel #1...")

    def close(self):
        """
        Closes browser instance safely without triggering the Web UI 'Log Out' action,
        thereby preserving the validity of the auth_key.
        """
        if self.driver:
            print("[*] Closing browser session safely (preserving server auth_key)...")
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None


if __name__ == "__main__":
    print("[*] Telegram Web Controller module loaded successfully.")
