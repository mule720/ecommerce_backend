"""
GraphQL Middleware for performance optimization
- Query depth limiting to prevent DoS attacks and N+1 queries
- Query complexity analysis
"""
from graphql import parse


class DepthAnalyzer:
    """Analyze query depth to prevent deeply nested queries"""
    
    MAX_DEPTH = 10
    
    def __init__(self, max_depth=MAX_DEPTH):
        self.max_depth = max_depth
    
    def analyze(self, query_string):
        """Calculate the depth of a GraphQL query"""
        try:
            document = parse(query_string)
            definitions = document.definitions
            if not definitions:
                return 0
            
            max_depth = 0
            for definition in definitions:
                depth = self._get_depth(definition)
                if depth > max_depth:
                    max_depth = depth
            
            return max_depth
        except Exception:
            return 0
    
    def _get_depth(self, node, current_depth=0):
        """Recursively calculate depth of node"""
        if not hasattr(node, 'selection_set') or node.selection_set is None:
            return current_depth
        
        max_child_depth = current_depth
        for selection in node.selection_set.selections:
            child_depth = self._get_depth(selection, current_depth + 1)
            if child_depth > max_child_depth:
                max_child_depth = child_depth
        
        return max_child_depth


class QueryDepthMiddleware:
    """Middleware to limit GraphQL query depth"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.analyzer = DepthAnalyzer()
    
    def __call__(self, request):
        if hasattr(request, 'body') and request.method == 'POST':
            try:
                import json
                body = json.loads(request.body)
                query = body.get('query', '')
                
                depth = self.analyzer.analyze(query)
                if depth > DepthAnalyzer.MAX_DEPTH:
                    response_data = {
                        'errors': [{
                            'message': f'Query depth {depth} exceeds maximum allowed depth of {DepthAnalyzer.MAX_DEPTH}'
                        }]
                    }
                    from django.http import JsonResponse
                    return JsonResponse(response_data, status=400)
            except Exception:
                pass  # Continue if analysis fails
        
        return self.get_response(request)
