import { Controller, Post } from "@nestjs/common";
import axios from "axios";

@Controller("orders")
export class OrdersController {
  @Post(":orderId/pay")
  async pay() {
    await axios.post("http://billing/api/v1/invoices", {});
  }
}
