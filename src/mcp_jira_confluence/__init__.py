from . import server

def main():
    """Main entry point for the package."""
    return server.main()

# Expose important items at package level
__all__ = ['main', 'server']