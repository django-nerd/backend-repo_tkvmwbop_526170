"""
Database Schemas for Arihant Automobiles E‑Commerce

Each Pydantic model represents a MongoDB collection. The collection name is the
lowercased class name (e.g., Product -> "product").
"""
from typing import List, Optional, Dict
from pydantic import BaseModel, Field, EmailStr


class Product(BaseModel):
    """Automobile product schema"""
    title: str = Field(..., description="Product title (e.g., 'Arihant GTX Alloy Wheel')")
    description: Optional[str] = Field(None, description="Detailed description")
    price: float = Field(..., ge=0, description="Price in INR")
    category: str = Field(..., description="Category (e.g., 'Sedan', 'SUV', 'Accessories')")
    brand: Optional[str] = Field("Arihant", description="Brand name")
    images: List[str] = Field(default_factory=list, description="Image URLs")
    stock: int = Field(0, ge=0, description="Units in stock")
    specifications: Dict[str, str] = Field(default_factory=dict, description="Key-value specs")
    featured: bool = Field(False, description="Showcase on home page")


class OrderItem(BaseModel):
    product_id: str = Field(..., description="Mongo ObjectId of product as string")
    title: str
    price: float
    quantity: int = Field(..., ge=1)
    image: Optional[str] = None


class Customer(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    address: str
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None


class Order(BaseModel):
    items: List[OrderItem]
    customer: Customer
    subtotal: float = Field(..., ge=0)
    shipping: float = Field(0, ge=0)
    total: float = Field(..., ge=0)
    status: str = Field("pending", description="pending | processing | shipped | delivered | cancelled")
    notes: Optional[str] = None
