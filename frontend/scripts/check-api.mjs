// Fails when src/api/schema.gen.ts is stale relative to ../openapi.yaml (run in CI).
import { execFileSync } from 'node:child_process';
import { readFileSync, rmSync } from 'node:fs';

const target = 'src/api/schema.gen.ts';
const temp = 'src/api/.schema.check.ts';
try {
  execFileSync('npx', ['openapi-typescript', '../openapi.yaml', '--default-non-nullable', 'false', '-o', temp], { stdio: 'ignore' });
  execFileSync('npx', ['prettier', '--write', temp], { stdio: 'ignore' });
  if (readFileSync(temp, 'utf8') !== readFileSync(target, 'utf8')) {
    console.error(`✖ ${target} is out of date with openapi.yaml. Run "npm run gen:api" and commit the result.`);
    process.exitCode = 1;
  } else {
    console.log(`✔ ${target} matches openapi.yaml`);
  }
} finally {
  rmSync(temp, { force: true });
}
