"""Bundled MCP protocol exercise: pure text statistics and UTC time only."""
from datetime import datetime,timezone
from mcp.server.fastmcp import FastMCP
mcp=FastMCP('Gongzhi Read-only Utilities')

@mcp.tool()
def text_metrics(text:str)->dict:
 """Count characters, lines and whitespace-separated words; no file or network I/O."""
 if len(text)>50000:raise ValueError('Text exceeds 50000 characters')
 return {'characters':len(text),'lines':len(text.splitlines()),'words':len(text.split()),'read_only':True}

@mcp.tool()
def utc_now()->dict:
 """Return the server's current UTC timestamp; no state changes."""
 return {'utc':datetime.now(timezone.utc).isoformat(),'read_only':True}

if __name__=='__main__':mcp.run(transport='stdio')
