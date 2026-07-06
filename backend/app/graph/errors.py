class GraphError(Exception):
    """Base exception for graph layer errors."""


class GraphBuildError(GraphError):
    """Raised when a ConversationGraph cannot be built from the provided data."""


class GraphTraversalError(GraphError):
    """Raised when a graph traversal fails."""


class SpeakerNotFoundError(GraphBuildError):
    """Raised when a referenced speaker ID does not exist in the graph."""
