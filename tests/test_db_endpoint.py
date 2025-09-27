#!/usr/bin/env python3
"""
Test database endpoint to debug the issue
"""

from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from config.database import get_db, get_db_session

app = FastAPI()

@app.get("/test-db")
async def test_db(db: Session = Depends(get_db)):
    """Test database connection"""
    try:
        # Test if db is a generator or session
        if hasattr(db, '__next__'):
            return {"error": "db is a generator", "type": str(type(db))}
        else:
            # Try to use it as a session
            result = db.execute("SELECT 1 as test").fetchone()
            return {"success": True, "result": result[0], "type": str(type(db))}
    except Exception as e:
        return {"error": str(e), "type": str(type(db))}

@app.get("/test-db-direct")
async def test_db_direct():
    """Test direct database connection"""
    try:
        db = get_db_session()
        result = db.execute("SELECT 1 as test").fetchone()
        return {"success": True, "result": result[0], "type": str(type(db))}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

