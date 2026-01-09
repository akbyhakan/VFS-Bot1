"""Simulate realistic human interactions using Bézier curves and random delays."""

import logging
import random
import asyncio
from typing import List, Tuple
from playwright.async_api import Page, Locator

try:
    import numpy as np
except ImportError:
    np = None

logger = logging.getLogger(__name__)


class HumanSimulator:
    """Simulate realistic human behavior patterns."""
    
    def __init__(self, config: dict = None):
        """
        Initialize human simulator.
        
        Args:
            config: Configuration dictionary with human behavior settings
        """
        self.config = config or {}
        self.mouse_steps = self.config.get('mouse_movement_steps', 20)
        self.typing_wpm_range = self.config.get('typing_wpm_range', [40, 80])
        self.click_delay_range = self.config.get('click_delay_range', [0.1, 0.5])
        self.random_actions = self.config.get('random_actions', True)
        
        if np is None:
            logger.warning("numpy not installed, using simplified movement calculations")
    
    @staticmethod
    def bezier_curve(start: Tuple[float, float], end: Tuple[float, float], 
                     steps: int = 20) -> List[Tuple[float, float]]:
        """
        Generate cubic Bézier curve points with random control points.
        
        Formula: B(t) = (1-t)³P₀ + 3(1-t)²tP₁ + 3(1-t)t²P₂ + t³P₃
        where t ∈ [0,1], P₀=start, P₃=end, P₁,P₂=random control points
        
        Args:
            start: Starting point (x, y)
            end: Ending point (x, y)
            steps: Number of points to generate
            
        Returns:
            List of (x, y) points along the curve
        """
        # Generate random control points
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        
        # Control point 1: random offset from start
        cp1_x = start[0] + dx * random.uniform(0.2, 0.4) + random.uniform(-50, 50)
        cp1_y = start[1] + dy * random.uniform(0.2, 0.4) + random.uniform(-50, 50)
        
        # Control point 2: random offset from end
        cp2_x = start[0] + dx * random.uniform(0.6, 0.8) + random.uniform(-50, 50)
        cp2_y = start[1] + dy * random.uniform(0.6, 0.8) + random.uniform(-50, 50)
        
        points = []
        
        if np is not None:
            # Use numpy for faster computation
            t_values = np.linspace(0, 1, steps)
            for t in t_values:
                # Cubic Bézier formula
                x = (1-t)**3 * start[0] + 3*(1-t)**2*t * cp1_x + 3*(1-t)*t**2 * cp2_x + t**3 * end[0]
                y = (1-t)**3 * start[1] + 3*(1-t)**2*t * cp1_y + 3*(1-t)*t**2 * cp2_y + t**3 * end[1]
                points.append((float(x), float(y)))
        else:
            # Fallback without numpy
            for i in range(steps):
                t = i / (steps - 1)
                # Cubic Bézier formula
                x = (1-t)**3 * start[0] + 3*(1-t)**2*t * cp1_x + 3*(1-t)*t**2 * cp2_x + t**3 * end[0]
                y = (1-t)**3 * start[1] + 3*(1-t)**2*t * cp1_y + 3*(1-t)*t**2 * cp2_y + t**3 * end[1]
                points.append((x, y))
        
        return points
    
    async def human_mouse_move(self, page: Page, target_x: float, target_y: float) -> None:
        """
        Move mouse along Bézier curve with 15-30 steps.
        
        Args:
            page: Playwright page object
            target_x: Target x coordinate
            target_y: Target y coordinate
        """
        try:
            # Get current mouse position (start from a random point if unknown)
            start_x = random.uniform(100, 500)
            start_y = random.uniform(100, 500)
            
            # Random number of steps between 15-30
            steps = random.randint(15, 30)
            
            # Generate Bézier curve
            points = self.bezier_curve((start_x, start_y), (target_x, target_y), steps)
            
            # Move along the curve
            for x, y in points:
                await page.mouse.move(x, y)
                # Random small delay between movements
                await asyncio.sleep(random.uniform(0.001, 0.005))
            
            logger.debug(f"Mouse moved to ({target_x}, {target_y}) in {steps} steps")
        except Exception as e:
            logger.error(f"Error in human mouse move: {e}")
    
    async def human_click(self, page: Page, selector: str) -> bool:
        """
        Click with random position within element and delays.
        
        Args:
            page: Playwright page object
            selector: Element selector
            
        Returns:
            True if click successful
        """
        try:
            # Wait for element
            element = page.locator(selector)
            await element.wait_for(state="visible", timeout=10000)
            
            # Get element bounding box
            box = await element.bounding_box()
            if not box:
                logger.error(f"Could not get bounding box for {selector}")
                return False
            
            # Random position within element (avoid edges)
            offset_x = random.uniform(box['width'] * 0.2, box['width'] * 0.8)
            offset_y = random.uniform(box['height'] * 0.2, box['height'] * 0.8)
            
            target_x = box['x'] + offset_x
            target_y = box['y'] + offset_y
            
            # Move mouse to target
            await self.human_mouse_move(page, target_x, target_y)
            
            # Random delay before click
            await asyncio.sleep(random.uniform(*self.click_delay_range))
            
            # Click
            await page.mouse.click(target_x, target_y)
            
            # Random delay after click
            await asyncio.sleep(random.uniform(0.05, 0.15))
            
            logger.debug(f"Human click on {selector}")
            return True
            
        except Exception as e:
            logger.error(f"Error in human click: {e}")
            return False
    
    async def human_type(self, page: Page, selector: str, text: str) -> bool:
        """
        Type at 40-80 WPM with character variation.
        
        Args:
            page: Playwright page object
            selector: Element selector
            text: Text to type
            
        Returns:
            True if typing successful
        """
        try:
            # Wait for element and click it
            element = page.locator(selector)
            await element.wait_for(state="visible", timeout=10000)
            await self.human_click(page, selector)
            
            # Calculate typing speed (WPM to delay per character)
            wpm = random.uniform(*self.typing_wpm_range)
            # Average word length is 5 characters
            chars_per_second = (wpm * 5) / 60
            base_delay = 1 / chars_per_second
            
            # Type each character with variation
            for char in text:
                await page.keyboard.type(char)
                # Add variation: ±30% of base delay
                delay = base_delay * random.uniform(0.7, 1.3)
                await asyncio.sleep(delay)
            
            logger.debug(f"Human typing completed at ~{wpm:.1f} WPM")
            return True
            
        except Exception as e:
            logger.error(f"Error in human type: {e}")
            return False
    
    async def random_scroll(self, page: Page) -> None:
        """Natural chunked scrolling."""
        try:
            # Random number of scroll chunks (3-7)
            chunks = random.randint(3, 7)
            
            for _ in range(chunks):
                # Random scroll distance (100-500 pixels)
                scroll_distance = random.randint(100, 500)
                
                # Scroll
                await page.mouse.wheel(0, scroll_distance)
                
                # Random pause between scrolls
                await asyncio.sleep(random.uniform(0.3, 0.8))
            
            logger.debug(f"Random scroll performed in {chunks} chunks")
        except Exception as e:
            logger.error(f"Error in random scroll: {e}")
    
    async def random_human_action(self, page: Page) -> None:
        """Perform random actions to simulate human behavior."""
        if not self.random_actions:
            return
        
        try:
            action = random.choice(['scroll', 'mouse_move', 'pause'])
            
            if action == 'scroll':
                await self.random_scroll(page)
            elif action == 'mouse_move':
                # Move mouse to random position
                x = random.uniform(200, 1200)
                y = random.uniform(200, 800)
                await self.human_mouse_move(page, x, y)
            elif action == 'pause':
                # Random pause
                await asyncio.sleep(random.uniform(1, 3))
            
            logger.debug(f"Random human action: {action}")
        except Exception as e:
            logger.error(f"Error in random human action: {e}")
