import os
from typing import List, Optional, Any
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Product as ProductSchema, Order as OrderSchema


class ObjectIdStr(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        try:
            ObjectId(str(v))
            return str(v)
        except Exception:
            raise ValueError("Invalid ObjectId")


class ProductOut(BaseModel):
    id: ObjectIdStr
    title: str
    description: Optional[str] = None
    price: float
    category: str
    brand: Optional[str] = None
    images: List[str] = []
    stock: int
    specifications: dict = {}
    featured: bool = False

    class Config:
        from_attributes = True


class OrderOut(BaseModel):
    id: ObjectIdStr
    total: float
    status: str
    items: list
    customer: dict


app = FastAPI(title="Arihant Automobiles API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_admin(x_admin_key: Optional[str] = Header(default=None)):
    admin_key = os.getenv("ADMIN_API_KEY")
    if not admin_key:
        # If not set, allow for development convenience
        return True
    if x_admin_key != admin_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")
    return True


@app.get("/")
def root():
    return {"name": "Arihant Automobiles API", "status": "ok"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "❌ Not Set",
        "database_name": "❌ Not Set",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Connected"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name
            response["collections"] = db.list_collection_names()
        else:
            response["database"] = "❌ Not Available"
    except Exception as e:
        response["database"] = f"⚠️ {str(e)[:80]}"
    return response


# -----------------
# Products Endpoints
# -----------------
@app.get("/api/products", response_model=List[ProductOut])
def list_products(
    q: Optional[str] = Query(default=None, description="Search query"),
    category: Optional[str] = None,
    featured: Optional[bool] = None,
    limit: int = 100,
):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    query: dict[str, Any] = {}
    if q:
        query["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
        ]
    if category:
        query["category"] = category
    if featured is not None:
        query["featured"] = featured

    docs = list(db["product"].find(query).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return docs


@app.post("/api/products", response_model=ObjectIdStr)
def create_product(payload: ProductSchema, _=require_admin()):
    new_id = create_document("product", payload)
    return new_id


@app.get("/api/products/{product_id}", response_model=ProductOut)
def get_product(product_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        doc = db["product"].find_one({"_id": ObjectId(product_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Product not found")
        doc["id"] = str(doc.pop("_id"))
        return doc
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product id")


@app.put("/api/products/{product_id}", response_model=ProductOut)
def update_product(product_id: str, payload: ProductSchema, _=require_admin()):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    data = payload.model_dump()
    data["updated_at"] = __import__("datetime").datetime.utcnow()
    res = db["product"].find_one_and_update(
        {"_id": ObjectId(product_id)},
        {"$set": data},
        return_document=True,
    )
    if not res:
        raise HTTPException(status_code=404, detail="Product not found")
    res["id"] = str(res.pop("_id"))
    return res


@app.delete("/api/products/{product_id}")
def delete_product(product_id: str, _=require_admin()):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    res = db["product"].delete_one({"_id": ObjectId(product_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"deleted": True}


# --------------
# Orders Endpoint
# --------------
@app.post("/api/orders", response_model=ObjectIdStr)
def create_order(order: OrderSchema):
    # Optionally validate items exist
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    # Reserve stock: ensure enough stock for each item
    for item in order.items:
        try:
            prod = db["product"].find_one({"_id": ObjectId(item.product_id)})
            if not prod:
                raise HTTPException(status_code=400, detail=f"Product not found: {item.product_id}")
            if prod.get("stock", 0) < item.quantity:
                raise HTTPException(status_code=400, detail=f"Insufficient stock for {prod['title']}")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid product id in order")

    # Deduct stock atomically per item
    for item in order.items:
        db["product"].update_one({"_id": ObjectId(item.product_id)}, {"$inc": {"stock": -item.quantity}})

    order_id = create_document("order", order)
    return order_id


@app.get("/api/orders", response_model=List[OrderOut])
def list_orders(_=require_admin(), limit: int = 100):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    docs = list(db["order"].find({}).sort("created_at", -1).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return docs
