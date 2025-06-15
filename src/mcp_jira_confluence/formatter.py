"""Formatting utilities for converting between Markdown and Jira/Confluence markup."""

import re
from typing import Optional


class JiraFormatter:
    """Convert between Markdown and Jira markup."""
    
    @staticmethod
    def markdown_to_jira(input_text: str) -> str:
        """Convert Markdown text to Jira markup."""
        output = input_text
        
        # Headers
        output = re.sub(r"^# (.*?)$", r"h1. \1", output, flags=re.MULTILINE)
        output = re.sub(r"^## (.*?)$", r"h2. \1", output, flags=re.MULTILINE)
        output = re.sub(r"^### (.*?)$", r"h3. \1", output, flags=re.MULTILINE)
        output = re.sub(r"^#### (.*?)$", r"h4. \1", output, flags=re.MULTILINE)
        output = re.sub(r"^##### (.*?)$", r"h5. \1", output, flags=re.MULTILINE)
        output = re.sub(r"^###### (.*?)$", r"h6. \1", output, flags=re.MULTILINE)
        
        # Bold and Italic
        output = re.sub(r"\*\*(.*?)\*\*", r"*\1*", output)  # Bold
        output = re.sub(r"__(.*?)__", r"*\1*", output)      # Bold
        output = re.sub(r"\*(.*?)\*", r"_\1_", output)      # Italic
        output = re.sub(r"_(.*?)_", r"_\1_", output)        # Italic
        
        # Lists
        # Bulleted lists
        output = re.sub(r"^- (.*?)$", r"* \1", output, flags=re.MULTILINE)
        output = re.sub(r"^\* (.*?)$", r"* \1", output, flags=re.MULTILINE)
        
        # Numbered lists
        output = re.sub(r"^(\d+)\. (.*?)$", r"# \2", output, flags=re.MULTILINE)
        
        # Code blocks
        output = re.sub(r"```(\w+)?\n(.*?)\n```", r"{code:\1}\2{code}", output, flags=re.DOTALL)
        output = re.sub(r"`([^`]+)`", r"{{{\1}}}", output)  # Inline code
        
        # Links
        output = re.sub(r"\[(.*?)\]\((.*?)\)", r"[\1|\2]", output)
        
        # Images
        output = re.sub(r"!\[(.*?)\]\((.*?)\)", r"!\2!", output)
        
        return output
    
    @staticmethod
    def jira_to_markdown(input_text: str) -> str:
        """Convert Jira markup to Markdown text."""
        output = input_text
        
        # Headers
        output = re.sub(r"^h1\. (.*?)$", r"# \1", output, flags=re.MULTILINE)
        output = re.sub(r"^h2\. (.*?)$", r"## \1", output, flags=re.MULTILINE)
        output = re.sub(r"^h3\. (.*?)$", r"### \1", output, flags=re.MULTILINE)
        output = re.sub(r"^h4\. (.*?)$", r"#### \1", output, flags=re.MULTILINE)
        output = re.sub(r"^h5\. (.*?)$", r"##### \1", output, flags=re.MULTILINE)
        output = re.sub(r"^h6\. (.*?)$", r"###### \1", output, flags=re.MULTILINE)
        
        # Bold and Italic
        output = re.sub(r"\*(.*?)\*", r"**\1**", output)  # Bold
        output = re.sub(r"_(.*?)_", r"*\1*", output)      # Italic
        
        # Lists
        # Bulleted lists
        output = re.sub(r"^\* (.*?)$", r"- \1", output, flags=re.MULTILINE)
        
        # Numbered lists
        output = re.sub(r"^# (.*?)$", r"1. \1", output, flags=re.MULTILINE)
        
        # Code blocks
        output = re.sub(r"\{code(?::\w+)?\}(.*?)\{code\}", r"```\n\1\n```", output, flags=re.DOTALL)
        output = re.sub(r"\{\{\{(.*?)\}\}\}", r"`\1`", output)  # Inline code
        
        # Links
        output = re.sub(r"\[(.*?)\|(.*?)\]", r"[\1](\2)", output)
        
        # Images
        output = re.sub(r"!(.*?)!", r"![](\1)", output)
        
        return output


class ConfluenceFormatter:
    """Convert between Markdown and Confluence markup."""
    
    @staticmethod
    def markdown_to_confluence(input_text: str) -> str:
        """Convert Markdown text to Confluence markup."""
        # Confluence supports most of Markdown syntax through its editor,
        # but for direct API calls we need to convert to Confluence storage format (XHTML)
        output = input_text
        
        # Headers
        output = re.sub(r"^# (.*?)$", r"<h1>\1</h1>", output, flags=re.MULTILINE)
        output = re.sub(r"^## (.*?)$", r"<h2>\1</h2>", output, flags=re.MULTILINE)
        output = re.sub(r"^### (.*?)$", r"<h3>\1</h3>", output, flags=re.MULTILINE)
        output = re.sub(r"^#### (.*?)$", r"<h4>\1</h4>", output, flags=re.MULTILINE)
        output = re.sub(r"^##### (.*?)$", r"<h5>\1</h5>", output, flags=re.MULTILINE)
        output = re.sub(r"^###### (.*?)$", r"<h6>\1</h6>", output, flags=re.MULTILINE)
        
        # Bold and Italic
        output = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", output)  # Bold
        output = re.sub(r"__(.*?)__", r"<strong>\1</strong>", output)      # Bold
        output = re.sub(r"\*(.*?)\*", r"<em>\1</em>", output)             # Italic
        output = re.sub(r"_(.*?)_", r"<em>\1</em>", output)               # Italic
        
        # Lists
        # This is a simplified implementation
        # Bulleted lists
        output = re.sub(r"^- (.*?)$", r"<ul><li>\1</li></ul>", output, flags=re.MULTILINE)
        output = re.sub(r"^* (.*?)$", r"<ul><li>\1</li></ul>", output, flags=re.MULTILINE)
        
        # Numbered lists
        output = re.sub(r"^(\d+)\. (.*?)$", r"<ol><li>\2</li></ol>", output, flags=re.MULTILINE)
        
        # Code blocks
        output = re.sub(r"```(\w+)?\n(.*?)\n```", r'<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">\1</ac:parameter><ac:plain-text-body><![CDATA[\2]]></ac:plain-text-body></ac:structured-macro>', output, flags=re.DOTALL)
        
        output = re.sub(r"`([^`]+)`", r'<code>\1</code>', output)  # Inline code
        
        # Links
        output = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2">\1</a>', output)
        
        # Images
        output = re.sub(r"!\[(.*?)\]\((.*?)\)", r'<ac:image><ri:url ri:value="\2"/></ac:image>', output)
        
        # Paragraphs - wrap remaining text in paragraph tags
        paragraphs = output.split("\n\n")
        processed_paragraphs = []
        for p in paragraphs:
            # Skip if the paragraph is already a tag
            if p.strip().startswith("<") and not p.strip().startswith("<em>") and not p.strip().startswith("<strong>") and not p.strip().startswith("<code>"):
                processed_paragraphs.append(p)
            else:
                # Wrap in paragraph tags
                processed_paragraphs.append(f"<p>{p}</p>")
                
        output = "\n\n".join(processed_paragraphs)
        
        # Ensure correct XHTML structure with XML namespace for Confluence
        output = f"<ac:structured-macro ac:name=\"html\"><ac:plain-text-body><![CDATA[{output}]]></ac:plain-text-body></ac:structured-macro>"
        
        return output
    
    @staticmethod
    def confluence_to_markdown(input_text: str) -> str:
        """Convert Confluence storage format to Markdown text."""
        # This is a simplified implementation
        output = input_text
        
        # Remove CDATA and macro wrapper if present
        output = re.sub(r'<ac:structured-macro[^>]*>.*?<!\[CDATA\[(.*?)\]\]>.*?</ac:structured-macro>', r'\1', output, flags=re.DOTALL)
        
        # Headers
        output = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1', output)
        output = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1', output)
        output = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1', output)
        output = re.sub(r'<h4[^>]*>(.*?)</h4>', r'#### \1', output)
        output = re.sub(r'<h5[^>]*>(.*?)</h5>', r'##### \1', output)
        output = re.sub(r'<h6[^>]*>(.*?)</h6>', r'###### \1', output)
        
        # Bold and Italic
        output = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', output)
        output = re.sub(r'<b[^>]*>(.*?)</b>', r'**\1**', output)
        output = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', output)
        output = re.sub(r'<i[^>]*>(.*?)</i>', r'*\1*', output)
        
        # Lists
        # This is simplified and might not handle nested lists properly
        output = re.sub(r'<ul[^>]*>.*?<li[^>]*>(.*?)</li>.*?</ul>', r'- \1', output)
        output = re.sub(r'<ol[^>]*>.*?<li[^>]*>(.*?)</li>.*?</ol>', r'1. \1', output)
        
        # Code blocks - simplified
        output = re.sub(r'<ac:structured-macro ac:name="code"[^>]*>.*?<ac:plain-text-body><!\[CDATA\[(.*?)\]\]></ac:plain-text-body></ac:structured-macro>', r'```\n\1\n```', output, flags=re.DOTALL)
        
        output = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', output)  # Inline code
        
        # Links
        output = re.sub(r'<a href="([^"]+)"[^>]*>(.*?)</a>', r'[\2](\1)', output)
        
        # Images
        output = re.sub(r'<ac:image[^>]*><ri:url ri:value="([^"]+)"[^>]*></ac:image>', r'![](\1)', output)
        output = re.sub(r'<img src="([^"]+)"[^>]*>', r'![](\1)', output)
        
        # Paragraphs
        output = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', output)
        
        # Clean up any remaining HTML tags (simplified)
        output = re.sub(r'<[^>]+>', '', output)
        
        # Fix multiple newlines
        output = re.sub(r'\n{3,}', '\n\n', output)
        
        return output.strip()
