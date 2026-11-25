package demo;

@RestController
@RequestMapping("/orders")
class OrderController {
    private final BillingClient billing;

    @PostMapping("/{orderId}/pay")
    public void pay() {
        billing.createInvoice("http://billing/api/v1/invoices");
    }
}

@FeignClient(name = "billing")
interface BillingClient {
    @PostMapping("/api/v1/invoices")
    void createInvoice(String body);
}
