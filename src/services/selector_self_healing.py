"""Gelişmiş selector self-healing sistemi."""
import logging
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from playwright.async_api import Page

logger = logging.getLogger(__name__)


class SelectorSelfHealing:
    """Kırık selector'ları otomatik tespit et ve onar."""
    
    CONFIDENCE_THRESHOLD = 0.80  # %80 güven skoru gerekli
    
    def __init__(
        self,
        selectors_file: str = "config/selectors.yaml",
        healing_log_file: str = "data/selector_healing_log.json"
    ):
        self.selectors_file = Path(selectors_file)
        self.healing_log_file = Path(healing_log_file)
        self.healing_log_file.parent.mkdir(parents=True, exist_ok=True)
        self._healing_history: List[Dict] = []
    
    async def attempt_heal(
        self,
        page: Page,
        selector_path: str,
        failed_selector: str,
        element_description: str
    ) -> Optional[str]:
        """Kırık selector'ı onarmaya çalış."""
        logger.info(f"🔧 Self-healing başlatılıyor: {selector_path}")
        
        # 1. Alternatif stratejiler dene
        candidates = await self._find_candidates(page, element_description)
        
        if not candidates:
            logger.warning(f"Aday selector bulunamadı: {selector_path}")
            return None
        
        # 2. Her aday için güven skoru hesapla
        for candidate in candidates:
            score = await self._calculate_confidence(page, candidate, element_description)
            
            if score >= self.CONFIDENCE_THRESHOLD:
                logger.info(f"✅ Yüksek güvenli aday bulundu: {candidate} (skor: {score:.2f})")
                
                # 3. YAML'ı güncelle
                await self._update_selectors_yaml(selector_path, candidate)
                
                # 4. Healing log'a kaydet
                self._log_healing(selector_path, failed_selector, candidate, score)
                
                return candidate
        
        logger.warning(f"Yeterli güvenli aday bulunamadı: {selector_path}")
        return None
    
    async def _find_candidates(self, page: Page, description: str) -> List[str]:
        """Element açıklamasına göre aday selector'lar bul."""
        candidates = []
        
        # Strateji 1: Text içeriğine göre ara
        keywords = description.lower().split()
        for keyword in keywords:
            if len(keyword) > 2:
                candidates.append(f"text={keyword}")
                candidates.append(f"*:has-text('{keyword}')")
        
        # Strateji 2: Yaygın input pattern'leri
        if "email" in description.lower():
            candidates.extend([
                "input[type='email']",
                "input[name*='email']",
                "input[id*='email']",
                "input[placeholder*='mail']"
            ])
        elif "password" in description.lower():
            candidates.extend([
                "input[type='password']",
                "input[name*='password']",
                "input[id*='password']"
            ])
        elif "button" in description.lower() or "submit" in description.lower():
            candidates.extend([
                "button[type='submit']",
                "button:has-text('Submit')",
                "button:has-text('Gönder')",
                "input[type='submit']"
            ])
        
        return candidates
    
    async def _calculate_confidence(
        self,
        page: Page,
        selector: str,
        description: str
    ) -> float:
        """Selector için güven skoru hesapla (0.0 - 1.0)."""
        score = 0.0
        
        try:
            # Element var mı?
            element = page.locator(selector)
            count = await element.count()
            
            if count == 0:
                return 0.0
            
            # Tek element = daha yüksek skor
            if count == 1:
                score += 0.4
            elif count <= 3:
                score += 0.2
            
            # Görünür mü?
            try:
                is_visible = await element.first.is_visible()
                if is_visible:
                    score += 0.3
            except:
                pass
            
            # Etkileşilebilir mi?
            try:
                is_enabled = await element.first.is_enabled()
                if is_enabled:
                    score += 0.2
            except:
                pass
            
            # Metin içeriği eşleşiyor mu?
            try:
                text = await element.first.text_content() or ""
                for keyword in description.lower().split():
                    if keyword in text.lower():
                        score += 0.1
                        break
            except:
                pass
            
        except Exception as e:
            logger.debug(f"Confidence hesaplama hatası: {e}")
            return 0.0
        
        return min(score, 1.0)
    
    async def _update_selectors_yaml(self, selector_path: str, new_selector: str) -> None:
        """Selectors YAML dosyasını güncelle."""
        try:
            if not self.selectors_file.exists():
                logger.warning("Selectors dosyası bulunamadı")
                return
            
            with open(self.selectors_file, 'r', encoding='utf-8') as f:
                selectors = yaml.safe_load(f)
            
            # Path'i parse et (örn: "login.email_input")
            parts = selector_path.split(".")
            
            # Mevcut fallback'lere ekle
            current = selectors
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            last_key = parts[-1]
            if last_key in current:
                existing = current[last_key]
                if isinstance(existing, dict):
                    # Fallback listesine ekle
                    if "fallbacks" not in existing:
                        existing["fallbacks"] = []
                    if new_selector not in existing["fallbacks"]:
                        existing["fallbacks"].insert(0, new_selector)  # Başa ekle
                        logger.info(f"Fallback eklendi: {selector_path} -> {new_selector}")
            
            with open(self.selectors_file, 'w', encoding='utf-8') as f:
                yaml.dump(selectors, f, allow_unicode=True, default_flow_style=False)
            
        except Exception as e:
            logger.error(f"YAML güncelleme hatası: {e}")
    
    def _log_healing(
        self,
        selector_path: str,
        old_selector: str,
        new_selector: str,
        confidence: float
    ) -> None:
        """Healing işlemini logla."""
        record = {
            "timestamp": datetime.now().isoformat(),
            "selector_path": selector_path,
            "old_selector": old_selector,
            "new_selector": new_selector,
            "confidence": confidence
        }
        self._healing_history.append(record)
        
        # Dosyaya kaydet
        try:
            import json
            existing = []
            if self.healing_log_file.exists():
                with open(self.healing_log_file, 'r') as f:
                    existing = json.load(f)
            existing.append(record)
            with open(self.healing_log_file, 'w') as f:
                json.dump(existing, f, indent=2)
        except Exception as e:
            logger.error(f"Healing log kaydetme hatası: {e}")
