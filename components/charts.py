import streamlit as st
import plotly.express as px

def polish_figure(figure, height=None):
    """Visual-only Plotly theme shared by every report visual."""
    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="#ffffff",
        font=dict(family="Inter, Segoe UI, Arial",color="#344054",size=12),
        margin=dict(l=18,r=18,t=24,b=18),height=height,
        legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="left",x=0,title_text="",maxheight=0.2),
        hoverlabel=dict(bgcolor="#10243e",font_color="white",bordercolor="#10243e"),
        xaxis=dict(gridcolor="#edf0f4",linecolor="#d9dee7",title_font=dict(size=12)),
        yaxis=dict(gridcolor="#edf0f4",linecolor="#d9dee7",title_font=dict(size=12)),
    )
    return figure


def chart(figure, height=420):
    st.plotly_chart(polish_figure(figure, height), width="stretch")
