from fastapi import APIRouter
import httpx

router = APIRouter(prefix="/orders")


@router.post("/{order_id}/pay")
async def pay(order_id: str):
    await httpx.AsyncClient().post("http://billing/api/v1/invoices")
