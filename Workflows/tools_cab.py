# Below are agent framework compatible tools for booking and cancelling a cab in a city.
# These tools can be used by an CabBookingAgent to book and cancel cab in a city. This Agent can be used by other agents 
# with A2A communication to book and cancel cabs in a city.

from typing import Annotated
from agent_framework import tool
from pydantic import Field

@tool(approval_mode="never_require")
def book_cab(
    pickup_location: Annotated[str, Field(description="The location where the cab should pick up the passenger")],
    dropoff_location: Annotated[str, Field(description="The location where the cab should drop off the passenger")], 
    pickup_date: Annotated[str, Field(description="The date when the cab should pick up the passenger (format: YYYY-MM-DD)")],
    pickup_time: Annotated[str, Field(description="The time when the cab should pick up the passenger (format: HH:MM:SS)")]
) -> str:
    """
    Books a cab from the specified pickup location to the dropoff location at the given pickup time.
    
    Args:
        pickup_location (str): The location where the cab should pick up the passenger
        dropoff_location (str): The location where the cab should drop off the passenger
        pickup_date (str): The date when the cab should pick up the passenger (format: YYYY-MM-DD)
        pickup_time (str): The time when the cab should pick up the passenger (format: HH   :MM:SS)
        
    Returns:
        str: A confirmation message with the booking details                    
    """
    # Mock data - in a real implementation, this would connect to a cab booking API
    cab_id = "C123123"
    driver_name = "John Doe"
    vehicle_type = "Sedan"
    price = 20
    
    result = f"Cab booked successfully!\n\n"
    result += f"Cab ID: {cab_id}\n"
    result += f"Driver Name: {driver_name}\n"
    result += f"Vehicle Type: {vehicle_type}\n"
    result += f"Price: ${price}\n"
    result += f"Pickup Location: {pickup_location}\n"
    result += f"Dropoff Location: {dropoff_location}\n"
    result += f"Pickup Date and Time: {pickup_date}T{pickup_time}\n"
    
    return result


@tool(approval_mode="never_require")
def cancel_cab(
    cab_id: Annotated[str, Field(description="The unique identifier of the cab booking to cancel")]
) -> str:
    """
    Cancels a previously booked cab.
    
    Args:
        cab_id (str): The unique identifier of the cab booking to cancel
        
    Returns:
        str: A confirmation message indicating the cancellation status
    """
    # Mock data - in a real implementation, this would connect to a cab booking API
    result = f"Cab with ID {cab_id} has been cancelled successfully."
    
    return result       
