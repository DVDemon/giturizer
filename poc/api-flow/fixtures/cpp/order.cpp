#include <string>
#include "billing_client.hpp"

constexpr std::string_view kName = "orders";

void createOrder() {
    BillingClient client;
    client.post("http://billing/api/v1/invoices");
}
