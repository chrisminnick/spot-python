"""Command-line interface for SPOT."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from .core.spot import SPOT
from .core.config import Config, get_config
from .utils.logger import configure_logging, get_logger


console = Console()


@click.group()
@click.option('--config', '-c', type=click.Path(exists=True), help='Config file path')
@click.option('--log-level', default='info', help='Log level')
@click.option('--provider', help='AI provider to use')
@click.pass_context
def cli(ctx, config, log_level, provider):
    """SPOT - Structured Prompt Output Toolkit."""
    # Initialize configuration
    if config:
        # Load custom config if provided
        pass  # Would implement custom config loading
    
    spot_config = get_config()
    
    # Override config with CLI options
    if log_level:
        spot_config.log_level = log_level
    if provider:
        spot_config.provider = provider
    
    # Configure logging
    configure_logging(
        log_level=spot_config.log_level,
        log_format=spot_config.log_format,
        log_outputs=spot_config.log_outputs_list,
        log_file=spot_config.log_file,
    )
    
    # Store config in context
    ctx.ensure_object(dict)
    ctx.obj['config'] = spot_config
    ctx.obj['spot'] = SPOT(spot_config)


@cli.command()
@click.pass_context
def health(ctx):
    """Check system health and component status."""
    async def run_health_check():
        spot = ctx.obj['spot']
        try:
            result = await spot.health_check()
            
            # Display results in a nice table
            table = Table(title="SPOT Health Check")
            table.add_column("Component", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Details")
            
            # Overall status
            status_color = "green" if result["status"] == "healthy" else "red"
            table.add_row("Overall", f"[{status_color}]{result['status'].upper()}[/{status_color}]", "")
            
            # Provider status
            for provider, healthy in result["providers"].items():
                status_text = "[green]HEALTHY[/green]" if healthy else "[red]UNHEALTHY[/red]"
                table.add_row(f"Provider: {provider}", status_text, "")
            
            # Templates
            template_status = "[green]AVAILABLE[/green]" if result["templates_available"] else "[red]MISSING[/red]"
            table.add_row("Templates", template_status, str(result["config"]["provider"]))
            
            console.print(table)
            
            if result["status"] != "healthy":
                sys.exit(1)
        
        except Exception as e:
            rprint(f"[red]Health check failed: {e}[/red]")
            sys.exit(1)
    
    asyncio.run(run_health_check())


@cli.command()
@click.argument('template')
@click.argument('input_file', type=click.Path(exists=True))
@click.argument('output_file', required=False)
@click.option('--provider', help='AI provider to use')
@click.option('--max-tokens', type=int, help='Maximum tokens to generate')
@click.option('--temperature', type=float, help='Generation temperature')
@click.pass_context
def generate(ctx, template, input_file, output_file, provider, max_tokens, temperature):
    """Generate content using a template."""
    async def run_generate():
        spot = ctx.obj['spot']
        
        try:
            kwargs = {}
            if max_tokens:
                kwargs['max_tokens'] = max_tokens
            if temperature:
                kwargs['temperature'] = temperature
            
            with console.status(f"Generating content with template {template}..."):
                result = await spot.generate(
                    template=template,
                    input_data=input_file,
                    output_file=output_file,
                    provider=provider,
                    **kwargs
                )
            
            rprint(f"[green]✓[/green] Content generated successfully!")
            rprint(f"Provider: {result.get('provider', 'unknown')}")
            rprint(f"Model: {result.get('model', 'unknown')}")
            
            if 'usage' in result:
                usage = result['usage']
                rprint(f"Tokens: {usage.get('total_tokens', 0)} total")
            
            if output_file:
                rprint(f"Output saved to: [cyan]{output_file}[/cyan]")
            else:
                # Display content preview
                content = result.get('content', '')
                preview = content[:200] + '...' if len(content) > 200 else content
                rprint(f"\nGenerated content:\n[dim]{preview}[/dim]")
        
        except Exception as e:
            rprint(f"[red]✗ Generation failed: {e}[/red]")
            sys.exit(1)
    
    asyncio.run(run_generate())


@cli.command()
@click.option('--template', help='Template to evaluate')
@click.option('--provider', help='Provider to evaluate')
@click.pass_context
def evaluate(ctx, template, provider):
    """Run evaluation tests."""
    async def run_evaluate():
        spot = ctx.obj['spot']
        
        try:
            with console.status("Running evaluation..."):
                result = await spot.evaluate(template=template, provider=provider)
            
            rprint(f"[green]✓[/green] Evaluation completed!")
            
            # Display results
            table = Table(title="Evaluation Results")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="yellow")
            
            table.add_row("Template", result["template"])
            table.add_row("Provider", result["provider"])
            table.add_row("Overall Score", f"{result['score']:.2%}")
            
            if 'metrics' in result:
                for metric, value in result['metrics'].items():
                    if isinstance(value, float):
                        table.add_row(metric.title(), f"{value:.2f}")
                    else:
                        table.add_row(metric.title(), str(value))
            
            console.print(table)
        
        except Exception as e:
            rprint(f"[red]✗ Evaluation failed: {e}[/red]")
            sys.exit(1)
    
    asyncio.run(run_evaluate())


@cli.command()
@click.pass_context
def validate(ctx):
    """Validate all templates and configurations."""
    async def run_validate():
        spot = ctx.obj['spot']
        
        try:
            with console.status("Validating templates..."):
                results = await spot.validate_templates()
            
            # Display results
            table = Table(title="Template Validation Results")
            table.add_column("Template", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Details")
            
            valid_count = 0
            for result in results:
                template_id = result.get("templateId", "unknown")
                status = result.get("status", "unknown")
                error = result.get("error", "")
                
                if status == "valid":
                    status_text = "[green]VALID[/green]"
                    valid_count += 1
                elif status == "invalid":
                    status_text = "[yellow]INVALID[/yellow]"
                else:
                    status_text = "[red]ERROR[/red]"
                
                table.add_row(template_id, status_text, error)
            
            console.print(table)
            rprint(f"\nValidation Summary: {valid_count}/{len(results)} templates valid")
            
            # Exit with error if any templates are invalid
            if valid_count < len(results):
                sys.exit(1)
        
        except Exception as e:
            rprint(f"[red]✗ Validation failed: {e}[/red]")
            sys.exit(1)
    
    asyncio.run(run_validate())


@cli.command()
@click.pass_context
def interactive(ctx):
    """Start interactive mode."""
    config = ctx.obj['config']
    spot = ctx.obj['spot']
    
    async def run_interactive():
        rprint("[cyan]🚀 SPOT Interactive Mode[/cyan]")
        rprint("Welcome to the Structured Prompt Output Toolkit!")
        rprint(f"Current provider: [yellow]{config.provider}[/yellow]")
        rprint("Type 'help' for available commands or 'quit' to exit.\n")
        
        while True:
            try:
                command = input("> ").strip().lower()
                
                if command == "quit" or command == "exit":
                    rprint("Goodbye! 👋")
                    break
                elif command == "help":
                    rprint("\nAvailable commands:")
                    rprint("  health    - Check system health")
                    rprint("  validate  - Validate templates")
                    rprint("  providers - List available providers")
                    rprint("  help      - Show this help")
                    rprint("  quit      - Exit interactive mode")
                elif command == "health":
                    result = await spot.health_check()
                    rprint(f"System status: [{'green' if result['status'] == 'healthy' else 'red'}]{result['status']}[/]")
                elif command == "validate":
                    results = await spot.validate_templates()
                    valid = sum(1 for r in results if r.get('status') == 'valid')
                    rprint(f"Templates: {valid}/{len(results)} valid")
                elif command == "providers":
                    providers = spot.provider_manager.list_providers()
                    rprint(f"Available providers: {', '.join(providers)}")
                else:
                    rprint(f"Unknown command: {command}. Type 'help' for available commands.")
                
                print()  # Empty line for readability
            
            except KeyboardInterrupt:
                rprint("\nGoodbye! 👋")
                break
            except EOFError:
                rprint("\nGoodbye! 👋")
                break
            except Exception as e:
                rprint(f"[red]Error: {e}[/red]")
    
    asyncio.run(run_interactive())


@cli.command()
@click.option('--host', default='0.0.0.0', help='Host to bind to')
@click.option('--port', default=8000, help='Port to bind to')
@click.option('--reload', is_flag=True, help='Enable auto-reload')
@click.pass_context
def web(ctx, host, port, reload):
    """Start web server."""
    try:
        import uvicorn
        from .web.app import create_app
        
        config = ctx.obj['config']
        app = create_app(config)
        
        rprint(f"Starting web server on [cyan]http://{host}:{port}[/cyan]")
        rprint("API documentation available at [cyan]/docs[/cyan]")
        
        uvicorn.run(
            app,
            host=host,
            port=port,
            reload=reload,
        )
    
    except ImportError as e:
        rprint(f"[red]Web server dependencies not available: {e}[/red]")
        rprint("Install with: pip install 'spot[web]'")
        sys.exit(1)
    except Exception as e:
        rprint(f"[red]Failed to start web server: {e}[/red]")
        sys.exit(1)


def main():
    """Main entry point."""
    # If no command provided, start interactive mode
    if len(sys.argv) == 1:
        sys.argv.append('interactive')
    
    cli()


if __name__ == '__main__':
    main()