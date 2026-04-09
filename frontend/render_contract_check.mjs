import { build } from 'esbuild'
import { writeFileSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { execFileSync } from 'node:child_process'

const root = path.dirname(fileURLToPath(import.meta.url))
const tempDir = mkdtempSync(path.join(root, '.tmp-render-'))
const entry = path.join(tempDir, 'entry.jsx')
const outfile = path.join(tempDir, 'bundle.cjs')

writeFileSync(entry, `
  import React from 'react'
  import { renderToStaticMarkup } from 'react-dom/server'
  import ResultDisplay from ${JSON.stringify(path.join(root, 'src/components/ResultDisplay.jsx'))}

  const cases = {
    success: {
      result: {
        analysis_status: 'success',
        validation_status: 'validated',
        is_preliminary: false,
        is_academic_submission: true,
        suggested_score: 10,
        max_score: 10,
        short_feedback: 'Validated summary',
        strengths: ['A', 'B'],
        mistakes: [],
        detailed_mistakes: [],
        improvement_suggestions: ['One suggestion'],
        next_steps: ['One', 'Two', 'Three'],
        validator_reason: 'Validated',
        analyzer_reason: 'Analyzer completed successfully.',
      }
    },
    validator_failed: {
      result: {
        analysis_status: 'validator_failed',
        validation_status: 'failed',
        is_preliminary: true,
        is_academic_submission: true,
        suggested_score: 9,
        max_score: 10,
        short_feedback: 'Preliminary summary',
        strengths: ['A', 'B'],
        mistakes: [],
        detailed_mistakes: [],
        improvement_suggestions: ['One suggestion'],
        next_steps: ['One', 'Two', 'Three'],
        validator_reason: 'Final validation was unavailable.',
        analyzer_reason: 'Analyzer completed successfully.',
      }
    },
    analyzer_failed: {
      result: {
        analysis_status: 'analyzer_failed',
        validation_status: 'failed',
        is_preliminary: false,
        is_academic_submission: true,
        suggested_score: null,
        max_score: null,
        short_feedback: 'Technical analysis failure. Please try again later.',
        strengths: [],
        mistakes: [],
        detailed_mistakes: [],
        improvement_suggestions: [],
        next_steps: [],
        validator_reason: 'Validation did not run.',
        analyzer_reason: 'Analyzer failed: test',
      }
    }
  }

  const rendered = Object.fromEntries(
    Object.entries(cases).map(([key, value]) => [
      key,
      renderToStaticMarkup(React.createElement(ResultDisplay, { result: value, onReset: () => {} }))
    ])
  )

  console.log(JSON.stringify({
    success: {
      hasValidatedBadge: rendered.success.includes('Validated by secondary AI reviewer'),
      hasPreliminaryText: rendered.success.includes('Preliminary analysis'),
      hasScore: rendered.success.includes('10/10')
    },
    validator_failed: {
      hasValidatedBadge: rendered.validator_failed.includes('Validated by secondary AI reviewer'),
      hasPreliminaryText: rendered.validator_failed.includes('Final validation was unavailable'),
      hasScore: rendered.validator_failed.includes('9/10')
    },
    analyzer_failed: {
      hasValidatedBadge: rendered.analyzer_failed.includes('Validated by secondary AI reviewer'),
      hasAnalysisFailedTitle: rendered.analyzer_failed.includes('Analysis Failed'),
      hasScore: rendered.analyzer_failed.includes('/10')
    }
  }))
`)

await build({
  entryPoints: [entry],
  bundle: true,
  platform: 'node',
  format: 'cjs',
  outfile,
  absWorkingDir: root,
  loader: { '.js': 'jsx', '.jsx': 'jsx' },
  jsx: 'automatic',
})

const output = execFileSync(process.execPath, [outfile], { encoding: 'utf8' })
process.stdout.write(output)
