import { render, screen } from '@testing-library/react';
import { EmptyState } from '@/components/layout/EmptyState';

describe('EmptyState', () => {
  it('renders title and description', () => {
    render(<EmptyState title="No sessions" description="Create your first session to get started." />);

    expect(screen.getByRole('heading', { name: 'No sessions' })).toBeInTheDocument();
    expect(screen.getByText('Create your first session to get started.')).toBeInTheDocument();
  });

  it('renders the CTA button when action is provided', () => {
    render(
      <EmptyState
        title="No sessions"
        action={<button>New Session</button>}
      />,
    );

    expect(screen.getByRole('button', { name: 'New Session' })).toBeInTheDocument();
  });

  it('does not render action container when action is not provided', () => {
    const { container } = render(<EmptyState title="No sessions" />);
    expect(container.querySelector('[class*="mt-2"]')).not.toBeInTheDocument();
  });

  it('renders icon when provided', () => {
    render(<EmptyState title="No sessions" icon={<span data-testid="custom-icon" />} />);
    expect(screen.getByTestId('custom-icon')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(<EmptyState title="No sessions" className="custom-class" />);
    expect(container.firstChild).toHaveClass('custom-class');
  });
});
