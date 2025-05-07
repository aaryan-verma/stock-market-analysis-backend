from fastapi import APIRouter, HTTPException, Depends, status, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
from pydantic import BaseModel, EmailStr, Field
import logging

from app.utils.email_service import email_service
from app.api.deps import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

class EmailPDFRequest(BaseModel):
    recipient_email: EmailStr
    stock_symbol: str
    pdf_data: str  # Base64 encoded PDF data
    plot_image: Optional[str] = None  # Base64 encoded image data
    analysis_summary: Optional[Dict[str, Any]] = None

# Background task function to send email
def send_email_task(
    recipient_email: str, 
    stock_symbol: str, 
    pdf_data: str,
    plot_image: Optional[str] = None,
    analysis_summary: Optional[Dict[str, Any]] = None
):
    """Background task for sending emails"""
    try:
        success = email_service.send_stock_analysis_pdf(
            recipient_email=recipient_email,
            stock_symbol=stock_symbol,
            pdf_data=pdf_data,
            plot_image=plot_image,
            analysis_summary=analysis_summary
        )
        
        if not success:
            logger.error(f"Email service failed to send email for {stock_symbol} to {recipient_email}")
        else:
            logger.info(f"Successfully sent analysis email for {stock_symbol} to {recipient_email}")
    except Exception as e:
        logger.error(f"Error in background email task: {str(e)}")

@router.post("/send-analysis", status_code=status.HTTP_202_ACCEPTED)
async def send_analysis_pdf(
    request: Request,
    background_tasks: BackgroundTasks,
    req_data: EmailPDFRequest
) -> JSONResponse:
    """
    Send a stock analysis PDF report via email asynchronously
    """
    try:
        # Log the request with important info (but not sensitive data)
        logger.info(f"Email request received for stock: {req_data.stock_symbol}, recipient: {req_data.recipient_email}")
        
        # Check authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            logger.warning(f"Invalid or missing authorization header for email request - {req_data.stock_symbol}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing authorization token"
            )
            
        # Validate that we have required data
        if not req_data.pdf_data:
            logger.warning(f"Missing PDF data in email request - {req_data.stock_symbol}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PDF data is required"
            )
        
        # Add email sending to background tasks
        background_tasks.add_task(
            send_email_task,
            recipient_email=req_data.recipient_email,
            stock_symbol=req_data.stock_symbol,
            pdf_data=req_data.pdf_data,
            plot_image=req_data.plot_image,
            analysis_summary=req_data.analysis_summary
        )
        
        logger.info(f"Email task added to background for {req_data.stock_symbol} to {req_data.recipient_email}")
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"message": f"Your analysis report for {req_data.stock_symbol} is being processed and will be sent to {req_data.recipient_email} shortly"}
        )
    
    except HTTPException as he:
        # Re-raise HTTP exceptions as they already have the right format
        raise he
    except Exception as e:
        logger.error(f"Error processing email request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing your request: {str(e)}"
        ) 