"""Captcha solving module with support for multiple providers."""

import asyncio
import logging
from typing import Any, Optional
from enum import Enum
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class CaptchaProvider(Enum):
    """Supported captcha solving providers."""

    TWOCAPTCHA = "2captcha"
    ANTICAPTCHA = "anticaptcha"
    NOPECHA = "nopecha"
    MANUAL = "manual"


class CaptchaSolver:
    """Multi-provider captcha solving service."""

    def __init__(self, provider: str, api_key: str = "", manual_timeout: int = 120):
        """
        Initialize captcha solver.

        Args:
            provider: Captcha provider name
            api_key: API key for the provider
            manual_timeout: Timeout for manual solving in seconds
        """
        self.provider = provider.lower()
        self.api_key = api_key
        self.manual_timeout = manual_timeout
        logger.info(f"CaptchaSolver initialized with provider: {self.provider}")

    async def solve_recaptcha(self, page: Page, site_key: str, url: str) -> Optional[str]:
        """
        Solve reCAPTCHA v2/v3.

        Args:
            page: Playwright page object
            site_key: reCAPTCHA site key
            url: Page URL

        Returns:
            Captcha solution token or None
        """
        logger.info(f"Solving reCAPTCHA with {self.provider}")

        if self.provider == CaptchaProvider.TWOCAPTCHA.value:
            return await self._solve_with_2captcha(site_key, url)
        elif self.provider == CaptchaProvider.ANTICAPTCHA.value:
            return await self._solve_with_anticaptcha(site_key, url)
        elif self.provider == CaptchaProvider.NOPECHA.value:
            return await self._solve_with_nopecha(page)
        elif self.provider == CaptchaProvider.MANUAL.value:
            return await self._solve_manually(page)
        else:
            logger.warning(f"Unknown provider: {self.provider}, falling back to manual")
            return await self._solve_manually(page)

    async def _solve_with_2captcha(self, site_key: str, url: str) -> Optional[str]:
        """
        Solve captcha using 2captcha service.

        Args:
            site_key: reCAPTCHA site key
            url: Page URL

        Returns:
            Captcha solution token
        """
        try:
            from twocaptcha import TwoCaptcha

            solver = TwoCaptcha(self.api_key)
            result: Any = solver.recaptcha(sitekey=site_key, url=url)
            logger.info("2captcha solved successfully")
            solution: str = result["code"]
            return solution
        except Exception as e:
            logger.error(f"2captcha error: {e}")
            return None

    async def _solve_with_anticaptcha(self, site_key: str, url: str) -> Optional[str]:
        """
        Solve captcha using anticaptcha service.

        Args:
            site_key: reCAPTCHA site key
            url: Page URL

        Returns:
            Captcha solution token
        """
        try:
            from anticaptchaofficial.recaptchav2proxyless import recaptchaV2Proxyless

            solver = recaptchaV2Proxyless()
            solver.set_key(self.api_key)
            solver.set_website_url(url)
            solver.set_website_key(site_key)

            g_response_result: Any = solver.solve_and_return_solution()
            g_response: str = g_response_result if isinstance(g_response_result, str) else ""
            if g_response != "0" and g_response:
                logger.info("Anticaptcha solved successfully")
                return g_response
            else:
                logger.error(f"Anticaptcha error: {solver.error_code}")
                return None
        except Exception as e:
            logger.error(f"Anticaptcha error: {e}")
            return None

    async def _solve_with_nopecha(self, page: Page) -> Optional[str]:
        """
        Solve captcha using nopecha extension.

        Args:
            page: Playwright page object

        Returns:
            Captcha solution token
        """
        try:
            # NopeCHA works as browser extension, wait for it to solve
            logger.info("Waiting for NopeCHA to solve captcha...")
            await asyncio.sleep(10)

            # Try to get the response token
            token_result = await page.evaluate(
                """
                () => {
                    const response = document.querySelector('[name="g-recaptcha-response"]');
                    return response ? response.value : null;
                }
            """
            )

            token: Optional[str] = token_result if isinstance(token_result, str) else None
            if token:
                logger.info("NopeCHA solved successfully")
                return token
            else:
                logger.warning("NopeCHA did not solve captcha in time")
                return None
        except Exception as e:
            logger.error(f"NopeCHA error: {e}")
            return None

    async def _solve_manually(self, page: Page) -> Optional[str]:
        """
        Wait for manual captcha solving.

        Args:
            page: Playwright page object

        Returns:
            Captcha solution token
        """
        logger.info(f"Waiting {self.manual_timeout}s for manual captcha solving...")

        try:
            # Wait for captcha response to be filled
            for i in range(self.manual_timeout):
                token_result = await page.evaluate(
                    """
                    () => {
                        const response = document.querySelector('[name="g-recaptcha-response"]');
                        return response ? response.value : null;
                    }
                """
                )

                token: Optional[str] = token_result if isinstance(token_result, str) else None
                if token:
                    logger.info("Manual captcha solved")
                    return token

                await asyncio.sleep(1)

            logger.warning("Manual captcha solving timeout")
            return None
        except Exception as e:
            logger.error(f"Manual solving error: {e}")
            return None

    async def solve_audio_captcha(self, audio_url: str) -> Optional[str]:
        """
        Solve audio captcha using speech recognition.

        Args:
            audio_url: URL to audio file

        Returns:
            Recognized text
        """
        try:
            import speech_recognition as sr
            import requests
            from pydub import AudioSegment
            import io

            # Download audio
            response = requests.get(audio_url)
            audio_data = io.BytesIO(response.content)

            # Convert to WAV if needed
            audio = AudioSegment.from_file(audio_data)
            wav_data = io.BytesIO()
            audio.export(wav_data, format="wav")
            wav_data.seek(0)

            # Recognize speech
            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_data) as source:
                audio_listened = recognizer.record(source)
                text_result: Any = recognizer.recognize_google(audio_listened)
                text: str = text_result if isinstance(text_result, str) else ""
                logger.info(f"Audio captcha solved: {text}")
                return text if text else None
        except Exception as e:
            logger.error(f"Audio captcha error: {e}")
            return None

    async def inject_captcha_solution(self, page: Page, token: str) -> bool:
        """
        Inject captcha solution token into page.

        Args:
            page: Playwright page object
            token: Captcha solution token

        Returns:
            True if successful
        """
        try:
            await page.evaluate(
                """(token) => {
                    const el = document.querySelector('[name="g-recaptcha-response"]');
                    if (el) {
                        el.value = token;
                        el.innerHTML = token;
                    }
                }""",
                token,
            )
            logger.info("Captcha solution injected")
            return True
        except Exception as e:
            logger.error(f"Failed to inject captcha solution: {e}")
            return False
