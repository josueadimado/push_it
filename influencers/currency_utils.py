"""
Currency conversion utilities for influencer wallet system.
"""
from decimal import Decimal
from brands.models import Currency


def convert_currency(amount, from_currency, to_currency):
    """
    Convert amount from one currency to another using exchange rates.
    
    Args:
        amount: Decimal amount to convert
        from_currency: Currency object or code to convert from
        to_currency: Currency object or code to convert to
    
    Returns:
        Decimal: Converted amount
    """
    if isinstance(from_currency, str):
        from_currency = Currency.objects.filter(code=from_currency).first()
    if isinstance(to_currency, str):
        to_currency = Currency.objects.filter(code=to_currency).first()
    
    if not from_currency or not to_currency:
        return amount
    
    # If same currency, no conversion needed
    if from_currency.code == to_currency.code:
        return amount
    
    # Get default currency for base conversion
    default_currency = Currency.get_default()
    if not default_currency:
        return amount
    
    # Convert to Decimal
    amount = Decimal(str(amount))
    
    # Convert from source currency to default currency
    # exchange_rate represents: 1 unit of this currency = exchange_rate units of default currency
    # e.g., if 1 USD = 1500 NGN (default), then USD.exchange_rate = 1500
    if from_currency.code != default_currency.code:
        # If source is not default, multiply by its exchange rate to get amount in default
        # e.g., 1 USD * 1500 = 1500 NGN (if exchange_rate is 1500)
        if from_currency.exchange_rate > 0:
            amount_in_default = amount * from_currency.exchange_rate
        else:
            amount_in_default = amount
    else:
        amount_in_default = amount
    
    # Convert from default currency to target currency
    if to_currency.code != default_currency.code:
        # If target is not default, divide by its exchange rate to get amount in target
        # e.g., 1500 NGN / 1500 = 1 USD (if exchange_rate is 1500)
        if to_currency.exchange_rate > 0:
            converted_amount = amount_in_default / to_currency.exchange_rate
        else:
            converted_amount = amount_in_default
    else:
        converted_amount = amount_in_default
    
    return converted_amount.quantize(Decimal('0.01'))  # Round to 2 decimal places

