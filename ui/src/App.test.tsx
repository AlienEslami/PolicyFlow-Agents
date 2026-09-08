import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { App } from './App'

describe('operator console', () => {
  it('communicates the synthetic boundary and workflow controls', () => {
    render(<App />)
    expect(screen.getByText('Synthetic operations workspace')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /run governed workflow/i })).toBeDisabled()
    expect(screen.getByText(/no claim decision is automated/i)).toBeInTheDocument()
  })
})
