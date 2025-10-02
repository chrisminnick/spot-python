"""Core SPOT functionality."""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .config import Config, get_config
from ..providers.manager import ProviderManager
from ..utils.logger import get_logger


class TemplateManager:
    """Manages prompt templates."""
    
    def __init__(self, templates_dir: Path):
        self.templates_dir = templates_dir
        self.logger = get_logger("template_manager")
        self._cache: Dict[str, Dict] = {}
    
    async def load_template(self, template_name: str) -> Dict[str, Any]:
        """Load a template by name."""
        if template_name in self._cache:
            return self._cache[template_name]
        
        template_path = self.templates_dir / f"{template_name}.json"
        
        if not template_path.exists():
            raise FileNotFoundError(f"Template {template_name} not found")
        
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template = json.load(f)
            
            self._cache[template_name] = template
            return template
        
        except Exception as e:
            self.logger.error(f"Failed to load template {template_name}: {e}")
            raise
    
    async def validate_template(self, template: Dict[str, Any]) -> bool:
        """Validate template structure."""
        required_fields = ["id", "version"]
        
        # Check required fields
        for field in required_fields:
            if field not in template:
                return False
        
        # Check that we have either 'prompt' or 'user' field for the actual prompt content
        if "prompt" not in template and "user" not in template:
            return False
        
        return True
    
    async def render_template(self, template: Dict[str, Any], variables: Dict[str, Any]) -> str:
        """Render template with variables."""
        # Get the prompt content - handle both old and new formats
        if "prompt" in template:
            prompt = template["prompt"]
        elif "user" in template:
            # For SPOT templates, combine system and user prompts
            system_prompt = template.get("system", "")
            user_prompt = template["user"]
            if system_prompt:
                prompt = f"{system_prompt}\n\n{user_prompt}"
            else:
                prompt = user_prompt
        else:
            raise ValueError("Template must contain either 'prompt' or 'user' field")
        
        # Simple variable substitution
        for key, value in variables.items():
            placeholder = f"{{{key}}}"
            prompt = prompt.replace(placeholder, str(value))
        
        return prompt


class EvaluationManager:
    """Manages evaluation and testing."""
    
    def __init__(self, golden_set_dir: Path):
        self.golden_set_dir = golden_set_dir
        self.logger = get_logger("evaluation_manager")
    
    async def run_evaluation(self, template_name: str, provider_name: str) -> Dict[str, Any]:
        """Run evaluation for a template and provider."""
        # This would implement the evaluation logic
        # For now, return a mock result
        return {
            "template": template_name,
            "provider": provider_name,
            "score": 0.85,
            "metrics": {
                "latency": 1.2,
                "token_efficiency": 0.9,
                "style_compliance": 0.8
            }
        }


class SPOT:
    """Main SPOT application class."""
    
    def __init__(self, config: Config = None):
        self.config = config or get_config()
        self.logger = get_logger("spot")
        
        # Initialize managers
        self.provider_manager = ProviderManager(self.config)
        self.template_manager = TemplateManager(self.config.templates_dir)
        self.evaluation_manager = EvaluationManager(self.config.golden_set_dir)
        
        self.logger.info("SPOT initialized successfully")
    
    async def generate(
        self,
        template: str,
        input_data: Union[Dict[str, Any], str, Path],
        output_file: Optional[Union[str, Path]] = None,
        provider: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate content using a template."""
        try:
            self.logger.info(f"Starting content generation with template: {template}")
            
            # Load template
            template_data = await self.template_manager.load_template(template)
            
            # Prepare input data
            if isinstance(input_data, (str, Path)):
                # Load from file
                input_path = Path(input_data)
                if input_path.suffix.lower() == '.json':
                    with open(input_path, 'r', encoding='utf-8') as f:
                        variables = json.load(f)
                else:
                    with open(input_path, 'r', encoding='utf-8') as f:
                        variables = {"content": f.read()}
            else:
                variables = input_data
            
            # Render template
            prompt = await self.template_manager.render_template(template_data, variables)
            
            # Generate content
            result = await self.provider_manager.generate(
                prompt=prompt,
                provider_name=provider,
                **kwargs
            )
            
            # Save output if specified
            if output_file:
                output_path = Path(output_file)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                if output_path.suffix.lower() == '.json':
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(result, f, indent=2)
                else:
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(result["content"])
            
            self.logger.info("Content generation completed successfully")
            return result
        
        except Exception as e:
            self.logger.error(f"Content generation failed: {e}")
            raise
    
    async def evaluate(
        self,
        template: Optional[str] = None,
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run evaluation tests."""
        try:
            self.logger.info("Starting evaluation")
            
            template = template or "draft_scaffold@1.0.0"
            provider = provider or self.config.provider
            
            result = await self.evaluation_manager.run_evaluation(template, provider)
            
            self.logger.info("Evaluation completed successfully")
            return result
        
        except Exception as e:
            self.logger.error(f"Evaluation failed: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform system health check."""
        try:
            self.logger.info("Running health check")
            
            # Check providers
            provider_health = await self.provider_manager.health_check_all()
            
            # Check templates directory
            templates_available = self.config.templates_dir.exists()
            
            # Overall status
            all_healthy = (
                any(provider_health.values()) and  # At least one provider healthy
                templates_available
            )
            
            result = {
                "status": "healthy" if all_healthy else "unhealthy",
                "providers": provider_health,
                "templates_available": templates_available,
                "config": {
                    "provider": self.config.provider,
                    "log_level": self.config.log_level,
                    "environment": self.config.environment
                }
            }
            
            self.logger.info(f"Health check completed: {result['status']}")
            return result
        
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            raise
    
    async def validate_templates(self) -> List[Dict[str, Any]]:
        """Validate all templates."""
        try:
            self.logger.info("Validating templates")
            
            results = []
            
            if not self.config.templates_dir.exists():
                return [{"error": "Templates directory not found"}]
            
            for template_file in self.config.templates_dir.glob("*.json"):
                template_name = template_file.stem
                try:
                    template_data = await self.template_manager.load_template(template_name)
                    is_valid = await self.template_manager.validate_template(template_data)
                    
                    results.append({
                        "templateId": template_name,
                        "status": "valid" if is_valid else "invalid"
                    })
                
                except Exception as e:
                    results.append({
                        "templateId": template_name,
                        "status": "error",
                        "error": str(e)
                    })
            
            self.logger.info(f"Template validation completed: {len(results)} templates checked")
            return results
        
        except Exception as e:
            self.logger.error(f"Template validation failed: {e}")
            raise