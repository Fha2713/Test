"""
IFS Translation Service - Enhanced with AI Support
Supports: Groq (free), Google Translate (free tier), and fallback dictionary
"""

from pathlib import Path
from typing import Dict, List, Optional, Union
import json
import os


class IFSTranslator:
    """AI-powered translator for IFS labels with multiple backend support"""
    
    # Language mappings
    LANGUAGE_NAMES = {
        'sv-SE': 'Swedish',
        'nb-NO': 'Norwegian Bokmål',
        'da-DK': 'Danish',
        'fi-FI': 'Finnish',
        'de-DE': 'German',
        'fr-FR': 'French',
        'es-ES': 'Spanish',
        'it-IT': 'Italian',
        'nl-NL': 'Dutch',
        'pt-PT': 'Portuguese',
        'pl-PL': 'Polish'
    }
    
    def __init__(self, backend='dictionary', api_key=None, dictionary_dir: Optional[Union[Path, str]] = None):
        """
        Initialize translator with specified backend
        
        Args:
            backend: 'groq', 'google', or 'dictionary' (default)
            api_key: API key for groq or google (optional)
            dictionary_dir: Optional path to project folder containing dictionary/
                            (e.g. dictionary/sv-SE.json). If set, dictionary backend
                            loads from these files; if not set, uses built-in terms.
        """
        self.backend = backend
        self.api_key = api_key or os.getenv('GROQ_API_KEY') or os.getenv('GOOGLE_API_KEY')
        self.dictionary_dir = Path(dictionary_dir) if dictionary_dir else None
        self.translation_cache = {}
        
        # Try to import backend-specific libraries
        if backend == 'groq':
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=self.api_key)
                print(f"[OK] Using Groq AI for translations (Model: llama-3.3-70b-versatile)")
            except ImportError:
                print("[WARN] Groq library not installed. Run: pip install groq")
                print("  Falling back to dictionary mode")
                self.backend = 'dictionary'
            except Exception as e:
                print(f"[WARN] Groq initialization failed: {e}")
                print("  Falling back to dictionary mode")
                self.backend = 'dictionary'
                
        elif backend == 'google':
            try:
                from googletrans import Translator
                self.google_translator = Translator()
                print(f"[OK] Using Google Translate for translations")
            except ImportError:
                print("[WARN] Google Translate library not installed. Run: pip install googletrans==4.0.0-rc1")
                print("  Falling back to dictionary mode")
                self.backend = 'dictionary'
            except Exception as e:
                print(f"[WARN] Google Translate initialization failed: {e}")
                print("  Falling back to dictionary mode")
                self.backend = 'dictionary'
        
        if self.backend == 'dictionary':
            if self.dictionary_dir:
                print(f"[OK] Using project dictionary from {self.dictionary_dir / 'dictionary'}")
            else:
                print(f"[OK] Using built-in dictionary for translations")
        
    def translate_batch(self, texts: List[str], target_language: str) -> Dict[str, str]:
        """
        Translate a batch of texts to target language
        
        Args:
            texts: List of English texts to translate
            target_language: Target language code (e.g., 'sv-SE')
            
        Returns:
            Dictionary mapping original text to translated text
        """
        translations = {}
        
        # Check cache first
        cache_key = target_language
        if cache_key not in self.translation_cache:
            self.translation_cache[cache_key] = {}
        
        texts_to_translate = []
        for text in texts:
            if text in self.translation_cache[cache_key]:
                translations[text] = self.translation_cache[cache_key][text]
            else:
                texts_to_translate.append(text)
        
        # Translate remaining texts
        if texts_to_translate:
            if self.backend == 'groq':
                new_translations = self._translate_with_groq(texts_to_translate, target_language)
            elif self.backend == 'google':
                new_translations = self._translate_with_google(texts_to_translate, target_language)
            else:
                new_translations = self._translate_with_dictionary(texts_to_translate, target_language)
            
            # Update cache and results
            for original, translated in new_translations.items():
                self.translation_cache[cache_key][original] = translated
                translations[original] = translated
        
        return translations
    
    def translate_single(self, text: str, target_language: str) -> str:
        """
        Translate a single text to target language
        
        Args:
            text: English text to translate
            target_language: Target language code (e.g., 'sv-SE')
            
        Returns:
            Translated text
        """
        result = self.translate_batch([text], target_language)
        return result.get(text, text)
    
    def _translate_with_groq(self, texts: List[str], target_language: str) -> Dict[str, str]:
        """
        Translate using Groq AI (free, fast)
        """
        language_name = self.LANGUAGE_NAMES.get(target_language, target_language)
        
        # Create translation prompt
        prompt = f"""You are translating IFS ERP system field labels from English to {language_name}.

Context:
- These are database field labels for an enterprise resource planning (ERP) system
- Maintain professional, enterprise-appropriate terminology
- Keep technical terms consistent with ERP/business software conventions
- Preserve special characters and formatting

Translate the following field labels to {language_name}:

{json.dumps(texts, indent=2)}

Return ONLY a valid JSON object mapping each English label to its {language_name} translation.
Format: {{"English Label": "{language_name} Translation", ...}}

Important rules:
1. Use standard ERP/business terminology
2. Keep abbreviations if they are universally understood (e.g., EAN, UOM, URL)
3. Translate descriptive terms appropriately
4. Maintain consistency across similar terms
5. Return ONLY the JSON object, no additional text"""

        try:
            chat_completion = self.groq_client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional translator specializing in ERP and business software terminology. You always return valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.3,  # Low temperature for consistency
                max_tokens=2000
            )
            
            response_text = chat_completion.choices[0].message.content.strip()
            
            # Try to extract JSON from response
            # Sometimes the model adds markdown code blocks
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0].strip()
            
            translations = json.loads(response_text)
            
            # Validate that all texts were translated
            for text in texts:
                if text not in translations:
                    translations[text] = text  # Fallback to original
            
            return translations
            
        except Exception as e:
            print(f"[WARN] Groq translation failed: {e}")
            print("  Falling back to dictionary")
            return self._translate_with_dictionary(texts, target_language)
    
    def _translate_with_google(self, texts: List[str], target_language: str) -> Dict[str, str]:
        """
        Translate using Google Translate (free tier)
        """
        # Get language code (e.g., 'sv' from 'sv-SE')
        lang_code = target_language.split('-')[0]
        
        translations = {}
        
        try:
            for text in texts:
                result = self.google_translator.translate(text, dest=lang_code, src='en')
                translations[text] = result.text
            
            return translations
            
        except Exception as e:
            print(f"[WARN] Google Translate failed: {e}")
            print("  Falling back to dictionary")
            return self._translate_with_dictionary(texts, target_language)
    
    def _load_dictionary_file(self, target_language: str) -> Dict[str, str]:
        """Load dictionary for a language from project folder. Returns {} if missing or invalid."""
        if not self.dictionary_dir:
            return {}
        path = self.dictionary_dir / "dictionary" / f"{target_language}.json"
        if not path.exists():
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _get_builtin_terms(self, target_language: str) -> Dict[str, str]:
        """Return built-in terms for backward compatibility when no dictionary_dir is set."""
        swedish_terms = {
            'Branch No': 'Filialnummer',
            'EAN': 'EAN',
            'Technical Description': 'Teknisk beskrivning',
            'Sales UOM': 'Försäljnings-enhet',
            'Package Measurement': 'Paketmått',
            'Min Order Qty': 'Min orderkvantitet',
            'List Price': 'Listpris',
            'Discount (%)': 'Rabatt (%)',
            'Stored Article': 'Lagrad artikel',
            'Product URL': 'Produkt-URL',
            'Account Reference': 'Kontoreferens',
            'Security Sheet': 'Säkerhetsdatablad',
            'Environmental Classification': 'Miljöklassificering',
            'Cross Reference': 'Korsreferens',
            "Supplier's Product Category 2": 'Leverantörens produktkategori 2',
            'Statistic Group': 'Statistikgrupp',
            'Part Synonym': 'Artikelsynonym',
            'Environmental Details': 'Miljödetaljer',
            'C Actual Cost': 'Verklig kostnad',
            'C Actual Revenue': 'Verklig intäkt',
            'Actual Cost': 'Verklig kostnad',
            'Actual Revenue': 'Verklig intäkt'
        }
        norwegian_terms = {
            'Branch No': 'Filialnummer',
            'EAN': 'EAN',
            'Technical Description': 'Teknisk beskrivelse',
            'Sales UOM': 'Salgsenhet',
            'Package Measurement': 'Pakkemål',
            'Min Order Qty': 'Min bestillingsmengde',
            'List Price': 'Listepris',
            'Discount (%)': 'Rabatt (%)',
            'Stored Article': 'Lagret artikkel',
            'Product URL': 'Produkt-URL',
            'Account Reference': 'Kontoreferanse',
            'Security Sheet': 'Sikkerhetsdatablad',
            'Environmental Classification': 'Miljøklassifisering',
            'Cross Reference': 'Kryssreferanse',
            "Supplier's Product Category 2": 'Leverandørens produktkategori 2',
            'Statistic Group': 'Statistikkgruppe',
            'Part Synonym': 'Artikkelsynonym',
            'Environmental Details': 'Miljødetaljer',
            'C Actual Cost': 'Faktisk kostnad',
            'C Actual Revenue': 'Faktisk inntekt',
            'Actual Cost': 'Faktisk kostnad',
            'Actual Revenue': 'Faktisk inntekt'
        }
        if target_language == 'sv-SE':
            return swedish_terms
        if target_language == 'nb-NO':
            return norwegian_terms
        return {}

    def _translate_with_dictionary(self, texts: List[str], target_language: str) -> Dict[str, str]:
        """
        Use dictionary: load from project folder if dictionary_dir is set, else built-in terms.
        If dictionary_dir is set but no file exists for the language, fall back to built-in.
        """
        if self.dictionary_dir:
            term_dict = self._load_dictionary_file(target_language)
            if not term_dict:
                term_dict = self._get_builtin_terms(target_language)
        else:
            term_dict = self._get_builtin_terms(target_language)
        translations = {}
        for text in texts:
            translations[text] = term_dict.get(text, text)
        return translations
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported language codes"""
        return list(self.LANGUAGE_NAMES.keys())


if __name__ == '__main__':
    # Test the translator with different backends
    test_texts = [
        'Branch No',
        'EAN',
        'Technical Description',
        'Sales UOM',
        'C Actual Cost',
        'C Actual Revenue'
    ]
    
    print("=" * 60)
    print("Testing IFS Translator")
    print("=" * 60)
    
    # Test with dictionary (default)
    print("\n1. Dictionary Backend:")
    translator = IFSTranslator(backend='dictionary')
    sv_translations = translator.translate_batch(test_texts, 'sv-SE')
    for eng, swe in sv_translations.items():
        print(f"  {eng} -> {swe}")
    
    # Test with Groq (if available)
    print("\n2. Groq AI Backend:")
    translator_groq = IFSTranslator(backend='groq')
    if translator_groq.backend == 'groq':
        sv_translations = translator_groq.translate_batch(test_texts[:3], 'sv-SE')
        for eng, swe in sv_translations.items():
            print(f"  {eng} -> {swe}")
    
    # Test with Google Translate (if available)
    print("\n3. Google Translate Backend:")
    translator_google = IFSTranslator(backend='google')
    if translator_google.backend == 'google':
        sv_translations = translator_google.translate_batch(test_texts[:3], 'sv-SE')
        for eng, swe in sv_translations.items():
            print(f"  {eng} -> {swe}")
