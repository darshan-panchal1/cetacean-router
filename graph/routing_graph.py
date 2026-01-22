from typing import TypedDict, List, Dict, Tuple, Annotated
from langgraph.graph import StateGraph, END
from agents.navigator import NavigatorAgent
from agents.biologist import BiologistAgent
from agents.risk_manager import RiskManagerAgent
import operator


class RoutingState(TypedDict):
    '''State shared across all nodes in the graph.'''
    # Input
    start_point: Tuple[float, float]
    end_point: Tuple[float, float]
    
    # Navigator outputs
    proposed_routes: Annotated[List[Dict], operator.add]
    
    # Biologist outputs
    risk_assessments: Annotated[List[Dict], operator.add]
    critical_sectors: List[Dict]
    
    # Risk Manager outputs
    selected_route: Dict
    decision_rationale: str
    llm_analysis: str
    approved: bool
    
    # Iteration control
    iteration_count: int
    max_iterations: int
    
    # MCP tool references (injected)
    obis_tool: callable
    route_calc_tool: callable


def create_routing_graph(obis_tool: callable, route_calc_tool: callable):
    '''
    Create the LangGraph workflow for route optimization.
    '''
    
    # Initialize agents
    navigator = NavigatorAgent()
    biologist = BiologistAgent()
    risk_manager = RiskManagerAgent()
    
    def navigator_node(state: RoutingState) -> RoutingState:
        '''Navigator proposes route options.'''
        print("\\n[Navigator Agent] Calculating route options...")
        
        start = state['start_point']
        end = state['end_point']
        
        # Calculate three route types
        direct_route = navigator.calculate_direct_route(start, end)
        
        # For detour and slow routes, we need risk info first
        # On first iteration, just propose direct route
        if state['iteration_count'] == 0:
            routes = [direct_route]
        else:
            # If critical sectors identified, propose alternatives
            if state.get('critical_sectors'):
                avoid_sector = state['critical_sectors'][0]
                detour_route = navigator.calculate_detour_route(
                    start, end, avoid_sector
                )
                slow_route = navigator.calculate_slow_route(
                    start, end, avoid_sector
                )
                routes = [direct_route, detour_route, slow_route]
            else:
                routes = [direct_route]
        
        # LLM reasoning
        nav_reasoning = navigator.reason_about_routes(routes)
        print(f"Navigator reasoning: {nav_reasoning}")
        
        return {
            **state,
            "proposed_routes": routes
        }
    
    def biologist_node(state: RoutingState) -> RoutingState:
        '''Biologist assesses risk for proposed routes.'''
        print("\\n[Biologist Agent] Assessing ecological risk...")
        
        routes = state['proposed_routes']
        risk_assessments = []
        all_critical_sectors = []
        
        for route in routes:
            waypoints = route['waypoints']
            
            # Assess overall route risk
            risk = biologist.assess_route_risk(waypoints, state['obis_tool'])
            risk_assessments.append(risk)
            
            print(f"  {route['route_name']}: {risk['risk_level']} "
                  f"({risk['sighting_count']} sightings)")
            
            # Identify critical sectors
            if risk['risk_level'] in ['HIGH', 'MEDIUM']:
                sectors = biologist.identify_critical_sectors(
                    waypoints, state['obis_tool']
                )
                all_critical_sectors.extend(sectors)
        
        return {
            **state,
            "risk_assessments": risk_assessments,
            "critical_sectors": all_critical_sectors
        }
    
    def risk_manager_node(state: RoutingState) -> RoutingState:
        '''Risk Manager evaluates and selects best route.'''
        print("\\n[Risk Manager Agent] Evaluating options...")
        
        routes = state['proposed_routes']
        risks = state['risk_assessments']
        
        # Make decision
        decision = risk_manager.evaluate_route_options(routes, risks)
        
        # Get LLM analysis
        llm_analysis = risk_manager.make_llm_decision(routes, risks)
        
        # Final approval
        approved = risk_manager.approve_route(
            decision['selected_route'],
            decision['risk_assessment']
        )
        
        print(f"\\nSelected: {decision['selected_route']['route_name']}")
        print(f"Score: {decision['composite_score']}/100")
        print(f"Approved: {approved}")
        
        return {
            **state,
            "selected_route": decision['selected_route'],
            "decision_rationale": decision['decision_rationale'],
            "llm_analysis": llm_analysis,
            "approved": approved,
            "iteration_count": state['iteration_count'] + 1
        }
    
    def should_continue(state: RoutingState) -> str:
        '''Decide whether to iterate or end.'''
        # End if approved or max iterations reached
        if state['approved']:
            return "end"
        
        if state['iteration_count'] >= state['max_iterations']:
            print("\\n[Warning] Max iterations reached, using best available route")
            return "end"
        
        # If not approved and high risk detected, iterate with alternatives
        if state['critical_sectors']:
            print("\\n[System] Iterating with alternative routes...")
            return "continue"
        
        return "end"
    
    # Build graph
    workflow = StateGraph(RoutingState)
    
    # Add nodes
    workflow.add_node("navigator", navigator_node)
    workflow.add_node("biologist", biologist_node)
    workflow.add_node("risk_manager", risk_manager_node)
    
    # Add edges
    workflow.set_entry_point("navigator")
    workflow.add_edge("navigator", "biologist")
    workflow.add_edge("biologist", "risk_manager")
    
    # Conditional edge for iteration
    workflow.add_conditional_edges(
        "risk_manager",
        should_continue,
        {
            "continue": "navigator",
            "end": END
        }
    )
    
    # Compile
    return workflow.compile()


def run_routing_optimization(
    start: Tuple[float, float],
    end: Tuple[float, float],
    obis_tool: callable,
    route_calc_tool: callable,
    max_iterations: int = 3
) -> Dict:
    '''
    Run the complete routing optimization workflow.
    
    Args:
        start: Starting coordinates (lat, lon)
        end: Ending coordinates (lat, lon)
        obis_tool: OBIS MCP tool function
        route_calc_tool: Route calculation MCP tool function
        max_iterations: Maximum optimization iterations
        
    Returns:
        Final routing decision
    '''
    print("\\n" + "="*60)
    print("CETACEAN-AWARE LOGISTICS ROUTER")
    print("="*60)
    print(f"Start: {start}")
    print(f"End: {end}")
    
    # Create graph
    graph = create_routing_graph(obis_tool, route_calc_tool)
    
    # Initial state
    initial_state = {
        "start_point": start,
        "end_point": end,
        "proposed_routes": [],
        "risk_assessments": [],
        "critical_sectors": [],
        "selected_route": {},
        "decision_rationale": "",
        "llm_analysis": "",
        "approved": False,
        "iteration_count": 0,
        "max_iterations": max_iterations,
        "obis_tool": obis_tool,
        "route_calc_tool": route_calc_tool
    }
    
    # Run workflow
    final_state = graph.invoke(initial_state)
    
    print("\\n" + "="*60)
    print("OPTIMIZATION COMPLETE")
    print("="*60)
    
    return final_state